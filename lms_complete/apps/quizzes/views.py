from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Avg, Count
from django.core.paginator import Paginator
from .models import Quiz, Question, QuizAttempt
from .forms import QuizForm, QuestionForm
from apps.courses.models import Lesson
from apps.enrollments.models import Enrollment
from .services.gemini_quiz_service import GeminiQuizGenerator
import json

# Instructor Views
@login_required
def manage_quizzes(request, lesson_id):
    """Manage quizzes for a lesson (instructor only)"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to manage quizzes.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    quiz = Quiz.objects.filter(lesson=lesson).first()
    
    return render(request, 'quizzes/manage_quizzes.html', {
        'lesson': lesson,
        'course': course,
        'quiz': quiz
    })


@login_required
def create_quiz(request, lesson_id):
    """Create a new quiz (instructor only)"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to create quizzes.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    # Check if quiz already exists
    existing_quiz = Quiz.objects.filter(lesson=lesson).first()
    if existing_quiz:
        messages.warning(request, 'A quiz already exists for this lesson. You can edit it instead.')
        return redirect('quizzes:edit_quiz', quiz_id=existing_quiz.id)
    
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.lesson = lesson
            quiz.save()
            messages.success(request, 'Quiz created successfully! Now add some questions.')
            return redirect('quizzes:manage_questions', quiz_id=quiz.id)
    else:
        form = QuizForm()
    
    return render(request, 'quizzes/quiz_form.html', {
        'form': form,
        'lesson': lesson,
        'course': course,
        'is_edit': False
    })


@login_required
def edit_quiz(request, quiz_id):
    """Edit an existing quiz (instructor only)"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to edit this quiz.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, 'Quiz updated successfully!')
            return redirect('quizzes:manage_questions', quiz_id=quiz.id)
    else:
        form = QuizForm(instance=quiz)
    
    return render(request, 'quizzes/quiz_form.html', {
        'form': form,
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'is_edit': True
    })


@login_required
def delete_quiz(request, quiz_id):
    """Delete a quiz (instructor only)"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to delete this quiz.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, 'Quiz deleted successfully!')
        return redirect('quizzes:manage_quizzes', lesson_id=lesson.id)
    
    return render(request, 'quizzes/quiz_confirm_delete.html', {
        'quiz': quiz,
        'lesson': lesson,
        'course': course
    })


@login_required
def manage_questions(request, quiz_id):
    """Manage questions for a quiz (instructor only)"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to manage questions.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    # Get questions ordered by 'order' field
    questions = quiz.questions.all().order_by('order')
    
    # Debug print
    print(f"Quiz: {quiz.title} (ID: {quiz.id})")
    print(f"Questions count: {questions.count()}")
    for q in questions:
        print(f"  Question {q.order}: {q.text[:30]}...")
    
    return render(request, 'quizzes/manage_questions.html', {
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'questions': questions
    })


@login_required
def add_question(request, quiz_id):
    """Add a question to a quiz (instructor only)"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to add questions.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            # Set the order to be the next number
            question.order = quiz.questions.count() + 1
            question.save()
            messages.success(request, 'Question added successfully!')
            return redirect('quizzes:manage_questions', quiz_id=quiz.id)
        else:
            # If form is invalid, print errors
            print("Form errors:", form.errors)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = QuestionForm()
    
    return render(request, 'quizzes/question_form.html', {
        'form': form,
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'is_edit': False
    })


@login_required
def edit_question(request, question_id):
    """Edit a question (instructor only)"""
    question = get_object_or_404(Question, id=question_id)
    quiz = question.quiz
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to edit this question.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, 'Question updated successfully!')
            return redirect('quizzes:manage_questions', quiz_id=quiz.id)
    else:
        form = QuestionForm(instance=question)
    
    return render(request, 'quizzes/question_form.html', {
        'form': form,
        'question': question,
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'is_edit': True
    })


@login_required
def delete_question(request, question_id):
    """Delete a question (instructor only)"""
    question = get_object_or_404(Question, id=question_id)
    quiz = question.quiz
    
    if request.method == 'POST':
        question.delete()
        
        # Reorder remaining questions
        for i, q in enumerate(quiz.questions.all().order_by('order')):
            q.order = i + 1
            q.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


@login_required
def take_quiz(request, lesson_id):
    """Take a quiz (student view)"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check if user is enrolled
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, 'You must be enrolled in this course to take the quiz.')
        return redirect('courses:course_detail', slug=course.slug)
    
    # Check if quiz exists
    quiz = Quiz.objects.filter(lesson=lesson, is_published=True).first()
    if not quiz:
        messages.error(request, 'No quiz available for this lesson.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    # Check attempts
    attempts_count = QuizAttempt.objects.filter(student=request.user, quiz=quiz).count()
    if quiz.max_attempts > 0 and attempts_count >= quiz.max_attempts:
        messages.error(request, f'You have reached the maximum number of attempts ({quiz.max_attempts}).')
        # Redirect to attempts history page
        return redirect('quizzes:my_attempts')
    
    # Check for in-progress attempt
    current_attempt = QuizAttempt.objects.filter(
        student=request.user,
        quiz=quiz,
        status='in_progress'
    ).first()
    
    if request.method == 'POST':
        if current_attempt:
            # Submit answers
            answers = {}
            total_questions = quiz.questions.count()
            answered_count = 0
            
            for key, value in request.POST.items():
                if key.startswith('question_'):
                    question_id = key.replace('question_', '')
                    answers[question_id] = value
                    answered_count += 1
            
            # Check if all questions are answered
            if answered_count < total_questions:
                messages.warning(request, f'You have answered {answered_count} out of {total_questions} questions. Please answer all questions.')
                return render(request, 'quizzes/take_quiz.html', {
                    'quiz': quiz,
                    'lesson': lesson,
                    'course': course,
                    'attempt': current_attempt,
                    'questions': quiz.questions.all().order_by('order'),
                    'time_remaining': current_attempt.get_time_remaining() if current_attempt else None
                })
            
            current_attempt.answers = answers
            current_attempt.completed_at = timezone.now()
            if current_attempt.started_at:
                current_attempt.time_taken = (current_attempt.completed_at - current_attempt.started_at).total_seconds()
            current_attempt.save()
            
            # Calculate score
            current_attempt.calculate_score()
            
            messages.success(request, f'Quiz submitted successfully! Your score: {current_attempt.percentage:.1f}%')
            # CORRECT REDIRECT - using attempt_id
            return redirect('quizzes:quiz_results', attempt_id=current_attempt.id)
    else:
        if not current_attempt:
            # Create new attempt
            current_attempt = QuizAttempt.objects.create(
                student=request.user,
                quiz=quiz,
                attempt_number=attempts_count + 1
            )
    
    # Get questions
    questions = quiz.questions.all().order_by('order')
    if quiz.shuffle_questions:
        import random
        questions = list(questions)
        random.shuffle(questions)
    
    return render(request, 'quizzes/take_quiz.html', {
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'attempt': current_attempt,
        'questions': questions,
        'time_remaining': current_attempt.get_time_remaining() if current_attempt else None
    })


@login_required
def quiz_results(request, attempt_id):
    """View quiz results"""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user)
    quiz = attempt.quiz
    lesson = quiz.lesson
    course = lesson.course
    
    questions = quiz.questions.all().order_by('order')
    
    # Prepare results for each question
    results = []
    for question in questions:
        user_answer = attempt.answers.get(str(question.id))
        is_correct = user_answer == question.correct_answer if user_answer else False
        
        results.append({
            'question': question,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'points': question.points if is_correct else 0
        })
    
    return render(request, 'quizzes/quiz_results.html', {
        'attempt': attempt,
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'results': results
    })


@login_required
def my_quiz_attempts(request):
    """View all quiz attempts by the student"""
    attempts = QuizAttempt.objects.filter(student=request.user).select_related(
        'quiz', 'quiz__lesson', 'quiz__lesson__course'
    ).order_by('-started_at')
    
    paginator = Paginator(attempts, 10)
    page = request.GET.get('page')
    attempts = paginator.get_page(page)
    
    return render(request, 'quizzes/my_attempts.html', {
        'attempts': attempts
    })


# Instructor Statistics
@login_required
def quiz_statistics(request, quiz_id):
    """View quiz statistics (instructor only)"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to view statistics.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    attempts = QuizAttempt.objects.filter(quiz=quiz, status='completed')
    total_attempts = attempts.count()
    
    # Statistics
    stats = {
        'total_attempts': total_attempts,
        'avg_score': attempts.aggregate(Avg('percentage'))['percentage__avg'] or 0,
        'highest_score': attempts.aggregate(models.Max('percentage'))['percentage__max'] or 0,
        'lowest_score': attempts.aggregate(models.Min('percentage'))['percentage__min'] or 0,
        'pass_count': attempts.filter(passed=True).count(),
        'fail_count': attempts.filter(passed=False).count(),
    }
    
    # Question statistics
    question_stats = []
    for question in quiz.questions.all().order_by('order'):
        correct_count = 0
        total_responses = 0
        
        for attempt in attempts:
            answer = attempt.answers.get(str(question.id))
            if answer:
                total_responses += 1
                if answer == question.correct_answer:
                    correct_count += 1
        
        question_stats.append({
            'question': question,
            'correct_count': correct_count,
            'total_responses': total_responses,
            'percentage': (correct_count / total_responses * 100) if total_responses > 0 else 0
        })
    
    return render(request, 'quizzes/quiz_statistics.html', {
        'quiz': quiz,
        'lesson': lesson,
        'course': course,
        'stats': stats,
        'question_stats': question_stats
    })

@login_required
def reorder_questions(request, quiz_id):
    """Reorder questions via drag and drop"""
    if request.method == 'POST':
        quiz = get_object_or_404(Quiz, id=quiz_id)
        lesson = quiz.lesson
        course = lesson.course
        
        # Check permission
        if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        import json
        data = json.loads(request.body)
        order = data.get('order', [])
        
        for index, question_id in enumerate(order):
            Question.objects.filter(id=question_id).update(order=index + 1)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

@login_required
def ai_generate_quiz(request, lesson_id):
    """AI-powered quiz generation page using Gemini"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user):
        messages.error(request, 'You do not have permission to generate quizzes for this lesson.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    # Check if quiz already exists
    existing_quiz = Quiz.objects.filter(lesson=lesson).first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'generate':
            num_questions = int(request.POST.get('num_questions', 5))
            difficulty = request.POST.get('difficulty', 'medium')
            
            # Store parameters in session
            request.session['ai_generation_params'] = {
                'num_questions': num_questions,
                'difficulty': difficulty
            }
            
            # Generate quiz using Gemini
            quiz_data = GeminiQuizGenerator.generate_quiz_from_lesson(
                lesson, 
                num_questions, 
                difficulty
            )
            
            if quiz_data['success']:
                # Store generated quiz in session for preview
                request.session['generated_quiz'] = quiz_data
                request.session['generated_quiz_lesson'] = lesson.id
                
                messages.success(request, 'Quiz generated successfully! Review and save it below.')
                return redirect('quizzes:preview_ai_quiz', lesson_id=lesson.id)
            else:
            # Check if it's a quota error
                if quiz_data.get('quota_error'):
                    messages.error(request, '⚠️ ' + quiz_data.get('error', 'API quota exceeded. Please try again later.'))
                else:
                    messages.error(request, f'AI generation failed: {quiz_data.get("error", "Unknown error")}')
        
        elif action == 'save_to_existing' and existing_quiz:
            # Generate additional questions for existing quiz
            num_questions = int(request.POST.get('num_questions', 3))
            difficulty = request.POST.get('difficulty', 'medium')
            
            # Get existing question texts
            existing_questions = list(existing_quiz.questions.values_list('text', flat=True))
            
            # Generate new questions
            result = GeminiQuizGenerator.generate_additional_questions(
                existing_questions,
                lesson,
                num_questions,
                difficulty
            )
            
            if result.get('success'):
                # Save new questions
                new_questions = []
                start_order = existing_quiz.questions.count() + 1
                
                for i, q_data in enumerate(result.get('questions', []), start_order):
                    options = q_data.get('options', {})
                    question = Question.objects.create(
                        quiz=existing_quiz,
                        text=q_data['text'],
                        points=1,
                        option_a=options.get('A', ''),
                        option_b=options.get('B', ''),
                        option_c=options.get('C', ''),
                        option_d=options.get('D', ''),
                        correct_answer=q_data.get('correct_answer', 'A'),
                        explanation=q_data.get('explanation', ''),
                        order=i,
                    )
                    new_questions.append(question)
                
                messages.success(request, f'{len(new_questions)} new questions added to existing quiz!')
                return redirect('quizzes:manage_questions', quiz_id=existing_quiz.id)
            else:
                messages.error(request, f'Failed to generate additional questions: {result.get("error", "Unknown error")}')
    
    return render(request, 'quizzes/ai_generate_quiz.html', {
        'lesson': lesson,
        'course': course,
        'existing_quiz': existing_quiz
    })


@login_required
def preview_ai_quiz(request, lesson_id):
    """Preview AI-generated quiz before saving"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user):
        messages.error(request, 'You do not have permission to view this quiz.')
        return redirect('courses:lesson_detail', course_slug=course.slug, lesson_id=lesson.id)
    
    # Get generated quiz from session
    quiz_data = request.session.get('generated_quiz')
    stored_lesson_id = request.session.get('generated_quiz_lesson')
    gen_params = request.session.get('ai_generation_params', {'difficulty': 'medium'})
    
    if not quiz_data or stored_lesson_id != lesson.id:
        messages.error(request, 'No generated quiz found. Please generate one first.')
        return redirect('quizzes:ai_generate_quiz', lesson_id=lesson.id)
    
    # Check if quiz already exists for this lesson
    existing_quiz = Quiz.objects.filter(lesson=lesson).first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save':
            if existing_quiz:
                # UPDATE existing quiz instead of creating new one
                existing_quiz.title = quiz_data.get('title', f'AI Generated Quiz - {lesson.title}')
                existing_quiz.description = f"AI-generated quiz using Gemini. Difficulty: {gen_params.get('difficulty', 'medium')}"
                existing_quiz.time_limit = 30
                existing_quiz.passing_score = 70
                existing_quiz.max_attempts = 3
                existing_quiz.is_published = False
                existing_quiz.save()
                
                # Delete existing questions
                existing_quiz.questions.all().delete()
                
                # Create new questions
                for i, q_data in enumerate(quiz_data['questions'], 1):
                    options = q_data.get('options', {})
                    Question.objects.create(
                        quiz=existing_quiz,
                        text=q_data['text'],
                        points=1,
                        option_a=options.get('A', ''),
                        option_b=options.get('B', ''),
                        option_c=options.get('C', ''),
                        option_d=options.get('D', ''),
                        correct_answer=q_data.get('correct_answer', 'A'),
                        explanation=q_data.get('explanation', ''),
                        order=i,
                    )
                
                messages.success(request, 'Quiz updated successfully!')
                quiz_id = existing_quiz.id
            else:
                # CREATE new quiz
                quiz = Quiz.objects.create(
                    lesson=lesson,
                    title=quiz_data.get('title', f'AI Generated Quiz - {lesson.title}'),
                    description=f"AI-generated quiz using Gemini. Difficulty: {gen_params.get('difficulty', 'medium')}",
                    time_limit=30,
                    passing_score=70,
                    max_attempts=3,
                    is_published=False,
                )
                
                # Create questions
                for i, q_data in enumerate(quiz_data['questions'], 1):
                    options = q_data.get('options', {})
                    Question.objects.create(
                        quiz=quiz,
                        text=q_data['text'],
                        points=1,
                        option_a=options.get('A', ''),
                        option_b=options.get('B', ''),
                        option_c=options.get('C', ''),
                        option_d=options.get('D', ''),
                        correct_answer=q_data.get('correct_answer', 'A'),
                        explanation=q_data.get('explanation', ''),
                        order=i,
                    )
                
                messages.success(request, 'Quiz created successfully!')
                quiz_id = quiz.id
            
            # Clear session data
            if 'generated_quiz' in request.session:
                del request.session['generated_quiz']
            if 'generated_quiz_lesson' in request.session:
                del request.session['generated_quiz_lesson']
            
            return redirect('quizzes:manage_questions', quiz_id=quiz_id)
        
        elif action == 'regenerate':
            # Redirect back to generation page
            return redirect('quizzes:ai_generate_quiz', lesson_id=lesson.id)
        
        elif action == 'cancel':
            # Clear session and redirect
            if 'generated_quiz' in request.session:
                del request.session['generated_quiz']
            if 'generated_quiz_lesson' in request.session:
                del request.session['generated_quiz_lesson']
            return redirect('quizzes:manage_quizzes', lesson_id=lesson.id)
    
    return render(request, 'quizzes/preview_ai_quiz.html', {
        'lesson': lesson,
        'course': course,
        'quiz_data': quiz_data,
        'existing_quiz': existing_quiz,  # Pass this to template
    })


@login_required
def ai_generate_more_questions(request, quiz_id):
    """AJAX endpoint to generate more questions for an existing quiz"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    lesson = quiz.lesson
    course = lesson.course
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        num_questions = int(data.get('num_questions', 3))
        difficulty = data.get('difficulty', 'medium')
        
        # Get existing question texts
        existing_questions = list(quiz.questions.values_list('text', flat=True))
        
        # Generate new questions
        result = GeminiQuizGenerator.generate_additional_questions(
            existing_questions,
            lesson,
            num_questions,
            difficulty
        )
        
        if result.get('success'):
            # Save new questions
            new_questions = []
            start_order = quiz.questions.count() + 1
            
            for i, q_data in enumerate(result.get('questions', []), start_order):
                options = q_data.get('options', {})
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data['text'],
                    points=1,
                    option_a=options.get('A', ''),
                    option_b=options.get('B', ''),
                    option_c=options.get('C', ''),
                    option_d=options.get('D', ''),
                    correct_answer=q_data.get('correct_answer', 'A'),
                    explanation=q_data.get('explanation', ''),
                    order=i,
                )
                new_questions.append({
                    'id': question.id,
                    'text': question.text,
                    'options': {
                        'A': question.option_a,
                        'B': question.option_b,
                        'C': question.option_c,
                        'D': question.option_d,
                    },
                    'correct_answer': question.correct_answer,
                    'explanation': question.explanation,
                })
            
            return JsonResponse({
                'success': True,
                'questions': new_questions,
                'count': len(new_questions)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Generation failed')
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

def debug_gemini_models(request):
    """Debug view to check available Gemini models"""
    try:
        import google.generativeai as genai
        from django.conf import settings
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        models = genai.list_models()
        
        available_models = []
        for model in models:
            available_models.append({
                'name': model.name,
                'display_name': model.display_name,
                'supported_methods': model.supported_generation_methods
            })
        
        return JsonResponse({
            'success': True,
            'api_key_configured': bool(settings.GEMINI_API_KEY),
            'api_key_preview': settings.GEMINI_API_KEY[:10] + '...' if settings.GEMINI_API_KEY else None,
            'models': available_models
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'api_key_configured': bool(settings.GEMINI_API_KEY)
        })