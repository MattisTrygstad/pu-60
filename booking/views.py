import calendar
from datetime import time

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.generic import DetailView

from booking.forms import ReservationForm
from booking.models import Course, BookingInterval, ReservationInterval, ReservationConnection
from itsBooking.templatetags.helpers import name


class CreateReservationView(DetailView):
    model = Course
    template_name = 'booking/course_detail.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context['weekdays'] = list(calendar.day_name)[0:5]
        intervals = []
        for hour in range(Course.OPEN_BOOKING_TIME, Course.CLOSE_BOOKING_TIME, Course.BOOKING_INTERVAL_LENGTH):
            booking_intervals = BookingInterval.objects.filter(Q(start=time(hour=hour)) & Q(course=self.object))
            interval = {
                'start': time(hour),
                'stop': time(hour + Course.BOOKING_INTERVAL_LENGTH),
                'booking_intervals': booking_intervals,
                'assistants': booking_intervals.first().assistants.values_list('id'),
                'reservation_intervals': [{
                    'start': time(hour=hour + (15 * i) // 60, minute=(15 * i) % 60),
                    'stop': time(hour=hour + (15 * (i + 1)) // 60, minute=(15 * (i + 1)) % 60),
                    'reservations': sorted(list(ReservationInterval.objects.filter(
                            Q(index=i) & Q(booking_interval__in=booking_intervals)
                        )), key=lambda r: r.booking_interval.day),
                    }
                    for i in range(Course.NUM_RESERVATIONS_IN_BOOKING_INTERVAL)
                ]
            }
            intervals.append(interval)
        context['intervals'] = intervals
        context['form'] = ReservationForm()
        print(self.object)
        # Assistants registered for a booking interval
        registered_assistants = []
        for booking_interval in BookingInterval.objects.filter(course = self.object):
            for assistant in booking_interval.assistants.all():
                registered_assistants.append(assistant)
        context['registered_assistants'] = list(set(registered_assistants))
        #DETTE BØR VÆRE UNØDVENDIG, FINN BEDRE LØSNING
        context['registered_assistants_count'] = len(list(set(registered_assistants)))

        #Share of reservation_intervals booked by students
        booked_counter = 0
        available_intervals = 0
        for booking_interval in BookingInterval.objects.filter(course=self.object):
            for reservation_interval in booking_interval.reservation_intervals.all():
                available_intervals += booking_interval.assistants.count()
                booked_counter += reservation_interval.connections.count()
        context['booked_ri_count'] = booked_counter
        context['available_rintervals_count'] = available_intervals


        #Share of full booking intervals
        full_booking_intervals = 0
        for booking_interval in BookingInterval.objects.filter(course=self.object):
            if booking_interval.max_available_assistants == booking_interval.assistants.count():
                full_booking_intervals += 1
        context['full_bi_count'] = full_booking_intervals
        context['available_bintervals_count'] = BookingInterval.objects.filter(course=self.object).all().count()
        context['available_assistants'] = Course.objects.get(pk=self.object.pk).assistants.all().count()
        context['total_opening_time'] = BookingInterval.objects.filter(Q(max_available_assistants__gt=0) & Q(course=self.object)).all().count()*2

        #Percentages for progress bar at cc_overview
        context['studass_percent'] = round(context['registered_assistants_count'] / context['available_assistants'] * 100)
        context['student_percent'] = round(context['booked_ri_count'] / context['available_rintervals_count'] * 100)
        context['max_studass_percent'] = round(context['full_bi_count'] / context['available_bintervals_count'] * 100)

        return context

    def post(self, request, *args, **kwargs):
        form = ReservationForm(request.POST, request.FILES)
        if request.user.groups.filter(name='students').exists():
            if form.is_valid():
                # create reservation
                reservation_interval = ReservationInterval.objects.get(pk=form.cleaned_data['reservation_pk'])
                reservation_connection = ReservationConnection.objects.create(
                    reservation_interval=reservation_interval, student=request.user
                )

                # add success message
                success_message = self.get_success_message(reservation_connection)
                if success_message:
                    messages.success(request, success_message)

                self.object = self.get_object()
                return self.render_to_response(context=self.get_context_data())
            else:
                # user message.error instead of form.errors, they force hidden form fields to be shown
                messages.error(request, 'Det oppsto en feil under opprettelsen av din reservajon. Vennligst prøv igjen.')
                return self.get(request, *args, **kwargs)
        else:
            raise PermissionDenied()

    def get_success_message(self, reservation_connection):
        return f'Reservasjon opprettet! Din stud. ass. er {name(reservation_connection.assistant)}'

class CcOverviewView(DetailView):
    template_name = 'cc_overview.html'
    context_object_name = 'registered_assistants'







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
        registration_available=False
    else:
        booking_interval.assistants.remove(request.user.id)
        registration_available = True
    available_assistants_count=booking_interval.assistants.all().count()
    data = {
        'registration_available': registration_available,
        'available_assistants_count': available_assistants_count,
    }
    return JsonResponse(data)


