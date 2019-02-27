from django.urls import path

from booking.views import BookingView, update_min_num_assistants

urlpatterns = [
    path('<str:slug>/', BookingView.as_view(), name='course_detail'),
    path('update', update_min_num_assistants, name='update_max_num_assistants'),
]
