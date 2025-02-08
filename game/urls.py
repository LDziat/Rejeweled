from django.urls import path
from game import views
from game.consumers import GameConsumer

urlpatterns = [
    path('', views.index, name='game_home'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    ]

websocket_urlpatterns = [
    path('ws/game/', GameConsumer.as_asgi()),
]