from django.urls import path
from . import views

app_name = 'quizzes'

urlpatterns = [
    # Instructor quiz management
    path('lesson/<int:lesson_id>/manage/', views.manage_quizzes, name='manage_quizzes'),
    path('lesson/<int:lesson_id>/create/', views.create_quiz, name='create_quiz'),
    path('<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    
    # Question management
    path('<int:quiz_id>/questions/', views.manage_questions, name='manage_questions'),
    path('<int:quiz_id>/questions/add/', views.add_question, name='add_question'),
    path('question/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('question/<int:question_id>/delete/', views.delete_question, name='delete_question'),
    
    # Student quiz taking
    path('take/<int:lesson_id>/', views.take_quiz, name='take_quiz'),
    path('attempt/<int:attempt_id>/results/', views.quiz_results, name='quiz_results'),
    path('my-attempts/', views.my_quiz_attempts, name='my_attempts'),
    
    # Statistics
    path('<int:quiz_id>/statistics/', views.quiz_statistics, name='quiz_statistics'),
    path('<int:quiz_id>/questions/reorder/', views.reorder_questions, name='reorder_questions'),

    # AI Quiz Generation URLs
    path('ai-generate/<int:lesson_id>/', views.ai_generate_quiz, name='ai_generate_quiz'),
    path('ai-preview/<int:lesson_id>/', views.preview_ai_quiz, name='preview_ai_quiz'),
    path('ai-generate-more/<int:quiz_id>/', views.ai_generate_more_questions, name='ai_generate_more'),
    path('debug-models/', views.debug_gemini_models, name='debug_models'),
]