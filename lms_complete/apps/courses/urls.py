from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.CourseListView.as_view(), name='course_list'),
    path('create/', views.CourseCreateView.as_view(), name='course_create'),
    
    # Analytics
    path('analytics/', views.instructor_analytics, name='instructor_analytics'),
    
    # Course detail
    path('<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('<int:pk>/edit/', views.CourseUpdateView.as_view(), name='course_update'),
    path('<int:pk>/delete/', views.CourseDeleteView.as_view(), name='course_delete'),
    
    # Student management
    path('<int:course_id>/students/', views.course_students, name='course_students'),
    
    # Lesson management
    path('<int:course_id>/lessons/', views.manage_lessons, name='manage_lessons'),
    path('<int:course_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('<int:course_id>/lessons/<int:lesson_id>/edit/', views.lesson_edit, name='lesson_edit'),
    path('<int:course_id>/lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    
    # File management
    path('lesson/<int:lesson_id>/files/', views.lesson_files, name='lesson_file'),
    path('lesson/<int:lesson_id>/upload/', views.upload_lesson_file, name='upload_lesson_file'),
    path('lesson/<int:lesson_id>/folder/create/', views.create_folder, name='create_folder'),
    path('folder/<int:folder_id>/', views.folder_detail, name='folder_detail'),
    path('folder/<int:folder_id>/upload/', views.upload_folder_file, name='upload_folder_file'),
    path('file/<int:file_id>/delete/', views.delete_file, name='delete_file'),
    path('folder-file/<int:file_id>/delete/', views.delete_folder_file, name='delete_folder_file'),
    path('folder/<int:folder_id>/delete/', views.delete_folder, name='delete_folder'),
    
    # REVIEW URLS
    path('<int:course_id>/reviews/add/', views.add_course_review, name='add_course_review'),
    path('<int:course_id>/instructor/<int:instructor_id>/review/', views.add_instructor_review, name='add_instructor_review'),
    path('reviews/<int:review_id>/helpful/', views.mark_review_helpful, name='mark_review_helpful'),
    path('<int:course_id>/reviews/load-more/', views.load_more_reviews, name='load_more_reviews'),
]