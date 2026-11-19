from django.urls import path

from windows import views

urlpatterns = [
    path("", views.explore, name="home"),
    path("windows/", views.window_list, name="window_list"),
    path("windows/new/", views.window_create, name="window_create"),
    path("windows/mine/", views.mine, name="mine"),
    path("windows/records/", views.records, name="records"),
    path("windows/records.csv", views.records_csv, name="records_csv"),
    path("windows/<int:pk>/", views.window_detail, name="window_detail"),
    path("windows/<int:pk>/confirm/", views.window_confirm, name="window_confirm"),
    path("windows/<int:pk>/complete/", views.window_complete, name="window_complete"),
    path("windows/<int:pk>/miss/", views.window_miss, name="window_miss"),
]
