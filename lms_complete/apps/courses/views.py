from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Course, Category, Lesson, LessonFile, LessonFolder, FolderFile, CourseReview, InstructorReview, ReviewHelpful
from .forms import LessonForm
from apps.enrollments.models import Enrollment
from apps.accounts.models import User
from apps.quizzes.models import QuizAttempt
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class InstructorRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to instructors only"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_instructor


class CourseListView(ListView):
    """List all published courses with filtering"""
    model = Course
    template_name = 'courses/courses_list.html'
    context_object_name = 'courses'
    paginate_by = 6
    
    def get_queryset(self):
        queryset = Course.objects.filter(status='published').select_related('instructor', 'category')
        
        # Search functionality
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search)
            )
        
        # Filter by category
        category = self.request.GET.get('category', '')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        # Filter by level
        level = self.request.GET.get('level', '')
        if level:
            queryset = queryset.filter(level=level)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.annotate(course_count=Count('courses'))
        context['levels'] = Course.LEVEL_CHOICES
        return context


class CourseDetailView(DetailView):
    """Display course details"""
    model = Course
    template_name = 'courses/courses_detail.html'
    context_object_name = 'course'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        
        # Check if user is enrolled
        if self.request.user.is_authenticated:
            context['is_enrolled'] = Enrollment.objects.filter(
                student=self.request.user,
                course=course
            ).exists()

            if context['is_enrolled'] and self.request.user.is_student:
                from .models import InstructorReview
                context['has_reviewed_instructor'] = InstructorReview.objects.filter(
                    instructor=course.instructor,
                    student=self.request.user,
                    course=course
                ).exists()
            else:
                context['has_reviewed_instructor'] = True
        

        
        # Get lessons with file counts
        lessons = course.lessons.all().order_by('order')
        for lesson in lessons:
            lesson.files_count = LessonFile.objects.filter(lesson=lesson).count()
        
        context['lessons'] = lessons
        context['total_duration'] = sum(lesson.duration_minutes for lesson in lessons)
        
        return context




class CourseCreateView(LoginRequiredMixin, InstructorRequiredMixin, CreateView):
    """Create a new course"""
    model = Course
    template_name = 'courses/courses_form.html'
    fields = ['title', 'description', 'short_description', 'category', 'level', 
              'thumbnail', 'price', 'is_free', 'status']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    def form_valid(self, form):
        form.instance.instructor = self.request.user
        response = super().form_valid(form)

        subject = "Course Created Successfully 🎉"
        message = f"""
Hi {self.request.user.get_full_name()},

Your course "{self.object.title}" has been created successfully.

You can now manage and publish it from your dashboard.

Thank you for teaching with us!
"""

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.request.user.email],
            fail_silently=False,
        )

        messages.success(self.request, 'Course created successfully! Email notification sent.')
        return response
    
    def get_success_url(self):
        return reverse_lazy('courses:course_detail', kwargs={'slug': self.object.slug})
    

class CourseUpdateView(LoginRequiredMixin, InstructorRequiredMixin, UpdateView):
    """Update an existing course"""
    model = Course
    template_name = 'courses/courses_form.html'
    fields = ['title', 'description', 'short_description', 'category', 'level', 
              'thumbnail', 'price', 'is_free', 'status']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    def get_queryset(self):
        
        return Course.objects.filter(instructor=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Course updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        
        return reverse_lazy('courses:course_detail', kwargs={'slug': self.object.slug})

class CourseDeleteView(LoginRequiredMixin, InstructorRequiredMixin, DeleteView):
    """Delete a course (instructor only)"""
    model = Course
    template_name = 'courses/course_confirm_delete.html'
    success_url = reverse_lazy('courses:course_list')
    
    def get_queryset(self):
        
        return Course.objects.filter(instructor=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        course = self.get_object()
        messages.success(request, f'Course "{course.title}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)
    

@login_required
def lesson_detail(request, course_slug, lesson_id):
    """Display lesson content with access control"""
    lesson = get_object_or_404(Lesson, course__slug=course_slug, id=lesson_id)
    course = lesson.course
    
    # Check access permissions
    can_access = False
    is_enrolled = False
    
    
    if lesson.is_free_preview:
        can_access = True
    
    # Case 2: User is authenticated
    elif request.user.is_authenticated:
        
        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course=course
        ).exists()
        
        print(f"DEBUG - User: {request.user.email}")
        print(f"DEBUG - Course: {course.title}")
        print(f"DEBUG - Is enrolled: {is_enrolled}")
        
        
        if request.user.is_instructor and course.instructor == request.user:
            can_access = True
        
        
        elif request.user.is_admin_user:
            can_access = True
        
        
        elif is_enrolled:
            can_access = True
    
    if not can_access:
        messages.error(request, 'Please enroll in this course to access this lesson.')
        return redirect('courses:course_detail', slug=course_slug)
    
    # Get all lessons for the sidebar
    all_lessons = list(course.lessons.all().order_by('order'))
    
    # Find current lesson index
    current_index = None
    for i, l in enumerate(all_lessons):
        if l.id == lesson.id:
            current_index = i
            break
    
    # Get next and previous lessons
    next_lesson = all_lessons[current_index + 1] if current_index is not None and current_index < len(all_lessons) - 1 else None
    prev_lesson = all_lessons[current_index - 1] if current_index is not None and current_index > 0 else None
    
    # Check which lessons are accessible for the sidebar
    accessible_lessons = []
    for l in all_lessons:
        l_accessible = (
            l.is_free_preview or 
            (request.user.is_authenticated and (
                (request.user.is_instructor and course.instructor == request.user) or
                request.user.is_admin_user or
                Enrollment.objects.filter(student=request.user, course=course).exists()
            ))
        )
        accessible_lessons.append({
            'lesson': l,
            'accessible': l_accessible
        })
    
    
    files_count = LessonFile.objects.filter(lesson=lesson).count()
    
    
    is_enrolled = Enrollment.objects.filter(
        student=request.user,
        course=course
    ).exists()
    
    print(f"FINAL DEBUG - Is enrolled: {is_enrolled}")
    
    context = {
        'lesson': lesson,
        'course': course,
        'next_lesson': next_lesson,
        'prev_lesson': prev_lesson,
        'all_lessons': all_lessons,
        'accessible_lessons': accessible_lessons,
        'current_index': current_index + 1 if current_index is not None else 1,
        'files_count': files_count,
        'is_enrolled': is_enrolled,  
    }
    
    return render(request, 'courses/lesson_detail.html', context)


@login_required
def manage_lessons(request, course_id):
    """Manage lessons for a course (instructor only)"""
    course = get_object_or_404(Course, id=course_id)
    
    
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to manage lessons for this course.')
        return redirect('courses:course_detail', slug=course.slug)
    
    lessons = course.lessons.all().order_by('order')
    
    return render(request, 'courses/manage_lessons.html', {
        'course': course,
        'lessons': lessons
    })


@login_required
def lesson_create(request, course_id):
    """Create a new lesson (instructor only)"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to add lessons to this course.')
        
        return redirect('courses:course_detail', slug=course.slug)
    
    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, 'Lesson created successfully!')
            return redirect('courses:manage_lessons', course_id=course.id)
    else:
        form = LessonForm()
    
    return render(request, 'courses/lesson_form.html', {
        'form': form,
        'course': course
    })


@login_required
def lesson_edit(request, course_id, lesson_id):
    """Edit an existing lesson (instructor only)"""
    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to edit this lesson.')
        #
        return redirect('courses:course_detail', slug=course.slug)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lesson updated successfully!')
            return redirect('courses:manage_lessons', course_id=course.id)
    else:
        form = LessonForm(instance=lesson)
    
    return render(request, 'courses/lesson_form.html', {
        'form': form,
        'course': course,
        'lesson': lesson
    })


@login_required
def lesson_delete(request, course_id, lesson_id):
    """Delete a lesson (instructor only)"""
    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to delete this lesson.')
        
        return redirect('courses:course_detail', slug=course.slug)
    
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, 'Lesson deleted successfully!')
        return redirect('courses:manage_lessons', course_id=course.id)
    
    return render(request, 'courses/lesson_confirm_delete.html', {
        'lesson': lesson
    })


@login_required
def course_students(request, course_id):
    """View all students enrolled in a course (instructor only)"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check permission
    if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
        messages.error(request, 'You do not have permission to view this page.')
        
        return redirect('courses:course_detail', slug=course.slug)
    
    enrollments = Enrollment.objects.filter(course=course).select_related('student').order_by('-enrolled_at')
    
    # Pagination
    paginator = Paginator(enrollments, 20)
    page = request.GET.get('page')
    enrollments = paginator.get_page(page)
    
    # Statistics
    total_students = enrollments.paginator.count
    completed_count = enrollments.paginator.object_list.filter(status='completed').count()
    in_progress_count = enrollments.paginator.object_list.filter(status='in_progress').count()
    
    return render(request, 'courses/course_students.html', {
        'course': course,
        'enrollments': enrollments,
        'total_students': total_students,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
    })


@login_required
def lesson_files(request, lesson_id):
    """View and manage lesson files"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    
    # Check access
    can_access = False
    if request.user.is_authenticated:
        
        if (request.user.is_instructor and course.instructor == request.user) or request.user.is_admin_user:
            can_access = True
        # Students need to be enrolled
        else:
            can_access = Enrollment.objects.filter(
                student=request.user,
                course=course
            ).exists()
    
    if not can_access:
        messages.error(request, 'You do not have access to these resources.')
        
        return redirect('courses:course_detail', slug=course.slug)
    
    files = LessonFile.objects.filter(lesson=lesson).order_by('-created_at')
    folders = LessonFolder.objects.filter(lesson=lesson).prefetch_related('files').order_by('name')
    
    return render(request, 'courses/lesson_file.html', {
        'lesson': lesson,
        'course': course,
        'files': files,
        'folders': folders,
    })


@login_required
def upload_lesson_file(request, lesson_id):
    """Upload a file to a lesson (instructor only)"""
    if request.method == 'POST':
        try:
            lesson = get_object_or_404(Lesson, id=lesson_id)
            course = lesson.course
            
            # Check permission
            if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
                messages.error(request, 'You do not have permission to upload files.')
                return redirect('courses:lesson_file', lesson_id=lesson.id)
            
            file = request.FILES.get('file')
            if file:
                
                if file.size > 100 * 1024 * 1024:
                    messages.error(request, 'File size too large. Maximum size is 100MB.')
                    return redirect('courses:lesson_file', lesson_id=lesson.id)
                
                
                existing_file = LessonFile.objects.filter(lesson=lesson, title=file.name).first()
                if existing_file:
                    messages.warning(request, f'A file named "{file.name}" already exists. It will be replaced.')
                    existing_file.delete()
                
                
                ext = file.name.split('.')[-1].lower() if '.' in file.name else ''
                file_type_map = {
                    'pdf': 'pdf',
                    'doc': 'doc',
                    'docx': 'doc',
                    'ppt': 'ppt',
                    
                }
                file_type = file_type_map.get(ext, 'other')
                
                # Create the file record
                lesson_file = LessonFile.objects.create(
                    lesson=lesson,
                    title=file.name,
                    file=file,
                    file_type=file_type,
                    file_size=file.size
                )
                
                messages.success(request, f'File "{file.name}" uploaded successfully!')
            else:
                messages.error(request, 'No file selected.')
            
            return redirect('courses:lesson_file', lesson_id=lesson.id)
            
        except Exception as e:
            
            print(f"Upload error: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error uploading file: {str(e)}')
            return redirect('courses:lesson_file', lesson_id=lesson.id)
    
    
    return redirect('courses:lesson_detail', course_slug=lesson.course.slug, lesson_id=lesson.id)


@login_required
def create_folder(request, lesson_id):
    """Create a new folder in a lesson (instructor only)"""
    if request.method == 'POST':
        try:
            lesson = get_object_or_404(Lesson, id=lesson_id)
            course = lesson.course
            
            # Check permission
            if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
                messages.error(request, 'You do not have permission to create folders.')
                return redirect('courses:lesson_file', lesson_id=lesson.id)
            
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            
            if name:
                
                existing_folder = LessonFolder.objects.filter(lesson=lesson, name=name).first()
                if existing_folder:
                    messages.warning(request, f'A folder named "{name}" already exists.')
                else:
                    folder = LessonFolder.objects.create(
                        lesson=lesson,
                        name=name,
                        description=description
                    )
                    messages.success(request, f'Folder "{name}" created successfully!')
            else:
                messages.error(request, 'Folder name is required.')
            
            return redirect('courses:lesson_file', lesson_id=lesson.id)
            
        except Exception as e:
            print(f"Folder creation error: {str(e)}")
            messages.error(request, f'Error creating folder: {str(e)}')
            return redirect('courses:lesson_file', lesson_id=lesson.id)
    
    return redirect('courses:lesson_detail', course_slug=lesson.course.slug, lesson_id=lesson.id)


@login_required
def folder_detail(request, folder_id):
    """View folder contents"""
    folder = get_object_or_404(LessonFolder, id=folder_id)
    lesson = folder.lesson
    course = lesson.course
    
    # Check access
    can_access = False
    if request.user.is_authenticated:
        if (request.user.is_instructor and course.instructor == request.user) or request.user.is_admin_user:
            can_access = True
        else:
            can_access = Enrollment.objects.filter(
                student=request.user,
                course=course
            ).exists()
    
    if not can_access:
        messages.error(request, 'You do not have access to these resources.')
        
        return redirect('courses:course_detail', slug=course.slug)
    
    files = folder.files.all().order_by('-created_at')
    
    return render(request, 'courses/folder_detail.html', {
        'folder': folder,
        'lesson': lesson,
        'course': course,
        'files': files,
    })


@login_required
def upload_folder_file(request, folder_id):
    """Upload a file to a folder (instructor only)"""
    if request.method == 'POST':
        try:
            folder = get_object_or_404(LessonFolder, id=folder_id)
            course = folder.lesson.course
            
            # Check permission
            if not (request.user.is_instructor and course.instructor == request.user) and not request.user.is_admin_user:
                messages.error(request, 'You do not have permission to upload files.')
                return redirect('courses:folder_detail', folder_id=folder.id)
            
            file = request.FILES.get('file')
            if file:
                # Check file size
                if file.size > 100 * 1024 * 1024:
                    messages.error(request, 'File size too large. Maximum size is 100MB.')
                    return redirect('courses:folder_detail', folder_id=folder.id)
                
                # Check if file with same name exists
                existing_file = FolderFile.objects.filter(folder=folder, title=file.name).first()
                if existing_file:
                    messages.warning(request, f'A file named "{file.name}" already exists. It will be replaced.')
                    existing_file.delete()
                
                folder_file = FolderFile.objects.create(
                    folder=folder,
                    title=file.name,
                    file=file,
                    file_size=file.size
                )
                messages.success(request, f'File "{file.name}" uploaded successfully!')
            else:
                messages.error(request, 'No file selected.')
            
            return redirect('courses:folder_detail', folder_id=folder.id)
            
        except Exception as e:
            print(f"Folder upload error: {str(e)}")
            messages.error(request, f'Error uploading file: {str(e)}')
            return redirect('courses:folder_detail', folder_id=folder.id)
    
    return redirect('courses:lesson_file', lesson_id=folder.lesson.id)


@login_required
def delete_file(request, file_id):
    """Delete a file (instructor only)"""
    if request.method == 'POST':
        try:
            file = get_object_or_404(LessonFile, id=file_id)
            course = file.lesson.course
            
            if (request.user.is_instructor and course.instructor == request.user) or request.user.is_admin_user:
                file_name = file.title
                file.delete()
                return JsonResponse({'success': True, 'message': f'File "{file_name}" deleted successfully.'})
            else:
                return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
def delete_folder_file(request, file_id):
    """Delete a file from a folder (instructor only)"""
    if request.method == 'POST':
        try:
            file = get_object_or_404(FolderFile, id=file_id)
            course = file.folder.lesson.course
            
            if (request.user.is_instructor and course.instructor == request.user) or request.user.is_admin_user:
                file_name = file.title
                folder_id = file.folder.id
                file.delete()
                return JsonResponse({'success': True, 'message': f'File "{file_name}" deleted successfully.'})
            else:
                return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
def delete_folder(request, folder_id):
    """Delete a folder and all its contents (instructor only)"""
    if request.method == 'POST':
        try:
            folder = get_object_or_404(LessonFolder, id=folder_id)
            course = folder.lesson.course
            
            if (request.user.is_instructor and course.instructor == request.user) or request.user.is_admin_user:
                folder_name = folder.name
                lesson_id = folder.lesson.id
                folder.delete()
                return JsonResponse({'success': True, 'message': f'Folder "{folder_name}" deleted successfully.'})
            else:
                return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


def load_courses_demo(request):
    """Generator demonstration - lazy loading courses"""
    courses = Course.objects.filter(status='published').iterator()
    
    # Generator usage example
    def course_generator():
        for course in courses:
            yield {
                'id': course.id,
                'title': course.title,
                'instructor': course.instructor.get_full_name(),
            }
    
    return JsonResponse({
        'courses': list(course_generator()),
        'message': 'Courses loaded using generator (lazy loading)'
    })

@login_required
def add_course_review(request, course_id):
    """Add or edit a course review"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check if user is enrolled
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, 'You must be enrolled in this course to leave a review.')
        return redirect('courses:course_detail', slug=course.slug)
    
    #
    existing_review = CourseReview.objects.filter(course=course, student=request.user).first()
    
    if request.method == 'POST':
        # Process the review form
        rating = request.POST.get('rating')
        title = request.POST.get('title', '')
        comment = request.POST.get('comment', '')
        would_recommend = request.POST.get('would_recommend') == 'on'
        difficulty_rating = request.POST.get('difficulty_rating')
        
        if existing_review:
            # Update existing review
            existing_review.rating = rating
            existing_review.title = title
            existing_review.comment = comment
            existing_review.would_recommend = would_recommend
            existing_review.difficulty_rating = difficulty_rating
            existing_review.save()
            messages.success(request, 'Your review has been updated!')
        else:
            # Create new review
            CourseReview.objects.create(
                course=course,
                student=request.user,
                rating=rating,
                title=title,
                comment=comment,
                would_recommend=would_recommend,
                difficulty_rating=difficulty_rating,
                is_verified=Enrollment.objects.filter(student=request.user, course=course, status='completed').exists()
            )
            messages.success(request, 'Thank you for your review!')
        
        return redirect('courses:course_detail', slug=course.slug)
    

    return render(request, 'courses/add_review.html', {
        'course': course,
        'existing_review': existing_review,
        'review_type': 'course'
    })


@login_required
def add_instructor_review(request, course_id, instructor_id):
    """Add a review for an instructor"""
    course = get_object_or_404(Course, id=course_id)
    instructor = get_object_or_404(User, id=instructor_id, user_type='instructor')
    
    # Check if user is enrolled
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, 'You must be enrolled in this course to review the instructor.')
        return redirect('courses:course_detail', slug=course.slug)
    
    
    existing_review = InstructorReview.objects.filter(
        instructor=instructor, 
        student=request.user, 
        course=course
    ).first()
    
    if request.method == 'POST':
        # Process instructor review
        rating = request.POST.get('rating')
        clarity_rating = request.POST.get('clarity_rating')
        responsiveness_rating = request.POST.get('responsiveness_rating')
        comment = request.POST.get('comment')
        
        if existing_review:
            existing_review.rating = rating
            existing_review.clarity_rating = clarity_rating
            existing_review.responsiveness_rating = responsiveness_rating
            existing_review.comment = comment
            existing_review.save()
            messages.success(request, 'Your instructor review has been updated!')
        else:
            InstructorReview.objects.create(
                instructor=instructor,
                student=request.user,
                course=course,
                rating=rating,
                clarity_rating=clarity_rating,
                responsiveness_rating=responsiveness_rating,
                comment=comment
            )
            messages.success(request, 'Thank you for reviewing the instructor!')
        
        return redirect('courses:course_detail', slug=course.slug)
    
    return render(request, 'courses/add_review.html', {
        'course': course,
        'instructor': instructor,
        'existing_review': existing_review,
        'review_type': 'instructor'
    })


@login_required
def mark_review_helpful(request, review_id):
    """Mark a review as helpful"""
    if request.method == 'POST':
        review = get_object_or_404(CourseReview, id=review_id)
        
        
        existing = ReviewHelpful.objects.filter(review=review, user=request.user).first()
        
        if existing:
            existing.delete()
            helpful_count = review.helpful_votes.count()
            return JsonResponse({
                'success': True, 
                'action': 'removed',
                'count': helpful_count
            })
        else:
            ReviewHelpful.objects.create(review=review, user=request.user)
            helpful_count = review.helpful_votes.count()
            return JsonResponse({
                'success': True, 
                'action': 'added',
                'count': helpful_count
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


def load_more_reviews(request, course_id):
    """Load more reviews via AJAX"""
    course = get_object_or_404(Course, id=course_id)
    page = int(request.GET.get('page', 1))
    per_page = 5
    
    reviews = CourseReview.objects.filter(course=course).select_related('student').order_by('-created_at')
    
    start = (page - 1) * per_page
    end = start + per_page
    reviews_page = reviews[start:end]
    
    data = []
    for review in reviews_page:
        data.append({
            'id': review.id,
            'student_name': review.student.get_full_name(),
            'rating': review.rating,
            'title': review.title,
            'comment': review.comment,
            'date': review.created_at.strftime('%B %d, %Y'),
            'helpful_count': review.helpful_votes.count(),
            'is_verified': review.is_verified,
        })
    
    return JsonResponse({
        'reviews': data,
        'has_more': end < reviews.count()
    })


@login_required
def instructor_analytics(request):
    """Analytics dashboard for instructors"""
    if not request.user.is_instructor:
        messages.error(request, 'Access denied. Instructors only.')
        return redirect('courses:course_list')
    
    # Get instructor's courses
    courses = Course.objects.filter(instructor=request.user)
    
    # Overall statistics
    total_courses = courses.count()
    total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
    total_enrollments = Enrollment.objects.filter(course__in=courses).count()
    total_lessons = Lesson.objects.filter(course__in=courses).count()
    
    # Average rating across all courses
    avg_rating = courses.aggregate(Avg('average_rating'))['average_rating__avg'] or 0
    
    # Course-specific statistics
    course_stats = []
    for course in courses:
        enrollments = Enrollment.objects.filter(course=course)
        completed = enrollments.filter(status='completed').count()
        in_progress = enrollments.filter(status='in_progress').count()
        
        # Safely get reviews count if reviews exist
        reviews_count = 0
        if hasattr(course, 'reviews'):
            reviews_count = course.reviews.count()
        
        course_stats.append({
            'course': course,
            'total_enrollments': enrollments.count(),
            'completed': completed,
            'in_progress': in_progress,
            'completion_rate': (completed / enrollments.count() * 100) if enrollments.count() > 0 else 0,
            'avg_rating': course.average_rating,
            'reviews_count': reviews_count,
        })
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_enrollments = Enrollment.objects.filter(
        course__in=courses,
        enrolled_at__gte=thirty_days_ago
    ).count()
    
    # Quiz statistics
    quiz_stats = []
    for course in courses:
        for lesson in course.lessons.all():
            if hasattr(lesson, 'quiz') and lesson.quiz:
                quiz = lesson.quiz
                attempts = QuizAttempt.objects.filter(quiz=quiz)
                if attempts.exists():
                    quiz_stats.append({
                        'course': course.title,
                        'lesson': lesson.title,
                        'quiz': quiz.title,
                        'total_attempts': attempts.count(),
                        'avg_score': attempts.aggregate(Avg('percentage'))['percentage__avg'] or 0,
                        'pass_rate': (attempts.filter(passed=True).count() / attempts.count() * 100) if attempts.count() > 0 else 0,
                    })
    
    context = {
        'total_courses': total_courses,
        'total_students': total_students,
        'total_enrollments': total_enrollments,
        'total_lessons': total_lessons,
        'avg_rating': round(avg_rating, 2),
        'recent_enrollments': recent_enrollments,
        'course_stats': course_stats,
        'quiz_stats': quiz_stats,
    }
    
    return render(request, 'courses/instructor_analytics.html', context)