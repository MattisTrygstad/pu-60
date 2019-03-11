import calendar
from datetime import time

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.generic import ListView, FormView, DetailView
from django.views.generic.base import View

from booking.forms import ReservationConnectionForm
from booking.models import Course, BookingInterval, ReservationInterval, ReservationConnection
from itsBooking.templatetags.helpers import name


WEEKDAYS = list(calendar.day_name)[0:5]


class StudentTableView(DetailView):
    model = Course
    template_name = 'booking/course_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['weekdays'] = WEEKDAYS
        intervals = []
        for hour in range(Course.OPEN_BOOKING_TIME, Course.CLOSE_BOOKING_TIME, Course.BOOKING_INTERVAL_LENGTH):
            booking_intervals = BookingInterval.objects.filter(Q(start=time(hour=hour)) & Q(course=self.object))
            interval = {
                'start': time(hour),
                'stop': time(hour + Course.BOOKING_INTERVAL_LENGTH),
                'booking_intervals': booking_intervals,
                'reservation_intervals': [{
                    'start': time(hour=hour + (15 * i) // 60, minute=(15 * i) % 60),
                    'stop': time(hour=hour + (15 * (i + 1)) // 60, minute=(15 * (i + 1)) % 60),
                    'reservations': [r.reservation_intervals.filter(index=i).first() for r in
                                     booking_intervals.prefetch_related('reservation_intervals')],
                    }
                    for i in range(Course.NUM_RESERVATIONS_IN_BOOKING_INTERVAL)
                ]
            }
            intervals.append(interval)
        context['intervals'] = intervals
        context['form'] = ReservationConnectionForm()
        return context

    def post(self, request, *args, **kwargs):
        return CreateReservationConnect.as_view()(request, *args, **kwargs)


class CreateReservationConnect(UserPassesTestMixin, FormView):
    form_class = ReservationConnectionForm

    def get_success_url(self):
        return reverse('course_detail', kwargs={'slug': self.kwargs['slug']})

    def test_func(self):
        return self.request.user.groups.filter(name='students').exists()

    def form_valid(self, form):
        reservation_interval = ReservationInterval.objects.get(pk=form.cleaned_data['reservation_pk'])
        reservation_connection = ReservationConnection.objects.create(
            reservation_interval=reservation_interval, student=self.request.user
        )
        success_message = f'Reservasjon opprettet! Din stud. ass. er {name(reservation_connection.assistant)}'
        messages.success(self.request, success_message)
        return super().form_valid(form)

    def form_invalid(self):
        error_message = 'Det oppsto en feil under opprettelsen av din reservajon. Vennligst prøv igjen.'
        messages.error(self.request, error_message)
        return super().form_invalid()


class CourseDetailDelegator(View):
    delegator = {
        'students': StudentTableView.as_view(),
#        'assistants': AssistantTableView.as_view(),
#        'course_coordinators': CourseCoordinatorTableView.as_view(),
    }

    def dispatch(self, request, *args, **kwargs):
        request_user_group = self.request.user.groups.first().name
        return self.delegator[request_user_group](request, *args, **kwargs)


def update_max_num_assistants(request):
    nk = request.GET.get('nk', None)
    num = request.GET.get('num', None)
    booking_interval = BookingInterval.objects.get(nk=nk)

    if request.user == booking_interval.course.course_coordinator:
        booking_interval.max_available_assistants = num
        booking_interval.save()
        return HttpResponse('')

    raise PermissionDenied()


def bi_registration_switch(request):
    nk = request.GET.get('nk', None)
    booking_interval = BookingInterval.objects.get(nk=nk)

    if not booking_interval.course.assistants.filter(id=request.user.id).exists():
        raise PermissionDenied()
    if not booking_interval.assistants.filter(id=request.user.id).exists():
        booking_interval.assistants.add(request.user.id)
        registration_available = False
    else:
        booking_interval.assistants.remove(request.user.id)
        registration_available = True
    available_assistants_count = booking_interval.assistants.all().count()
    data = {
        'registration_available': registration_available,
        'available_assistants_count': available_assistants_count,
    }
    return JsonResponse(data)


class ReservationList(UserPassesTestMixin, ListView):
    template_name = 'booking/reservation_list.html'

    def get_queryset(self):
        return ReservationConnection.objects.filter(student=self.request.user)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data()
        context.update({'days': WEEKDAYS})
        return context

    def test_func(self):
        return self.request.user.groups.filter(name="students").exists()
