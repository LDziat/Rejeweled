from django.urls import path
from game import views

urlpatterns = [
    path('', views.index, name='game_home'),
]

