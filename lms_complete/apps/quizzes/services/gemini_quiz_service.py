import google.generativeai as genai
import json
import re
from django.conf import settings
from django.core.cache import cache

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


class GeminiQuizGenerator:
    """AI-powered quiz generator using Google Gemini API"""
    
    # Available models from your list
    AVAILABLE_MODELS = [
        'models/gemini-2.5-flash',  # Fast, efficient model
        'models/gemini-flash-latest',  # Latest flash
        'models/gemini-2.5-pro',    # Pro model for better quality
        'models/gemini-pro-latest',  # Latest pro
        'models/gemini-2.0-flash',  # Fallback option
    ]
    
    @staticmethod
    def generate_quiz_from_lesson(lesson, num_questions=5, difficulty='medium'):
        """
        Generate quiz questions from lesson content using Gemini
        """
        # Check cache first
        cache_key = f"quiz_{lesson.id}_{num_questions}_{difficulty}"
        cached_result = cache.get(cache_key)
        if cached_result:
            print(f"✅ Returning cached quiz for lesson {lesson.id}")
            return cached_result
        
        # Combine all content from the lesson
        content_parts = []
        
        # Add lesson title and description
        if lesson.title:
            content_parts.append(f"Lesson: {lesson.title}")
        if lesson.description:
            content_parts.append(f"Description: {lesson.description}")
        
        # Add lesson content (if available)
        if hasattr(lesson, 'content') and lesson.content:
            import re as regex
            # Strip HTML tags for cleaner text
            clean_text = regex.sub('<.*?>', '', lesson.content)
            # Limit content length to avoid token limits - REDUCED to 1000
            if len(clean_text) > 1000:
                clean_text = clean_text[:1000] + "..."
            content_parts.append(f"Content: {clean_text}")
        
        combined_text = "\n".join(content_parts)
        
        if not combined_text or len(combined_text.strip()) < 50:
            return {
                'success': False,
                'error': 'Lesson content is too short to generate meaningful questions'
            }
        
        # Prepare the prompt - SIMPLIFIED to avoid JSON parsing errors
        prompt = f"""
        Based on the following educational content, create a {difficulty} difficulty multiple-choice quiz with exactly {num_questions} questions.

        Content:
        {combined_text}

        Return ONLY a valid JSON object with this structure. No other text, no markdown, no backticks.
        
        {{
            "title": "A descriptive title for this quiz",
            "questions": [
                {{
                    "text": "Question text here",
                    "options": {{
                        "A": "First option",
                        "B": "Second option",
                        "C": "Third option",
                        "D": "Fourth option"
                    }},
                    "correct_answer": "A",
                    "explanation": "Brief explanation"
                }}
            ]
        }}
        """
        
        # Try models in order of preference
        last_error = None
        quota_error = False
        
        # Prioritize models - try 2.5 flash first (fastest)
        models_to_try = [
            'models/gemini-2.5-flash',
            'models/gemini-flash-latest',
            'models/gemini-2.5-pro',
            'models/gemini-pro-latest',
            'models/gemini-2.0-flash',
        ]
        
        for model_name in models_to_try:
            try:
                print(f"Trying Gemini model: {model_name}")
                
                # Get the generative model
                model = genai.GenerativeModel(model_name)
                
                # Set generation config for consistent JSON output
                generation_config = {
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                }
                
                # Generate content
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                # Extract text from response
                content = response.text
                
                # Clean the response - remove any markdown code blocks
                content = re.sub(r'```json\s*', '', content)
                content = re.sub(r'```\s*', '', content)
                content = content.strip()
                
                # Find JSON in the response
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    quiz_data = json.loads(json_str)
                else:
                    # Try to parse entire response as JSON
                    quiz_data = json.loads(content)
                
                # Validate quiz data structure
                if 'questions' not in quiz_data or not quiz_data['questions']:
                    continue
                
                # Validate each question has required fields
                validated_questions = []
                for q in quiz_data['questions']:
                    if all(k in q for k in ['text', 'options', 'correct_answer']):
                        # Ensure options have all 4 letters
                        options = q.get('options', {})
                        if 'A' not in options:
                            options['A'] = 'Option A'
                        if 'B' not in options:
                            options['B'] = 'Option B'
                        if 'C' not in options:
                            options['C'] = 'Option C'
                        if 'D' not in options:
                            options['D'] = 'Option D'
                        
                        validated_questions.append({
                            'text': q['text'],
                            'options': options,
                            'correct_answer': q['correct_answer'],
                            'explanation': q.get('explanation', 'No explanation provided.')
                        })
                
                if len(validated_questions) == 0:
                    continue
                
                # Prepare final quiz data
                quiz_data = {
                    'success': True,
                    'title': quiz_data.get('title', f"{lesson.title} - {difficulty.capitalize()} Quiz"),
                    'questions': validated_questions[:num_questions]  # Limit to requested number
                }
                
                print(f"✅ Successfully generated {len(validated_questions)} questions with {model_name}")
                
                # Cache the result for 1 hour
                cache.set(cache_key, quiz_data, timeout=3600)
                
                return quiz_data
                
            except Exception as e:
                error_str = str(e)
                last_error = error_str
                print(f"❌ Error with model {model_name}: {error_str}")
                
                # Check for quota errors
                if '429' in error_str or 'quota' in error_str.lower():
                    quota_error = True
                
                continue
        
        # If all models fail
        if quota_error:
            return {
                'success': False,
                'error': 'Daily API limit reached. Please try again tomorrow or set up billing in Google Cloud Console.',
                'quota_error': True
            }
        else:
            return {
                'success': False,
                'error': f'Failed to generate quiz. Last error: {last_error}'
            }
    
    @staticmethod
    def generate_additional_questions(existing_questions, lesson, num_questions=3, difficulty='medium'):
        """
        Generate additional questions that are different from existing ones
        """
        # Check cache
        cache_key = f"additional_questions_{lesson.id}_{num_questions}_{difficulty}_{len(existing_questions)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Get lesson content - REDUCED length
        content_parts = []
        if lesson.title:
            content_parts.append(f"Lesson: {lesson.title}")
        if lesson.description:
            content_parts.append(f"Description: {lesson.description}")
        if hasattr(lesson, 'content') and lesson.content:
            import re as regex
            clean_text = regex.sub('<.*?>', '', lesson.content)
            if len(clean_text) > 1000:
                clean_text = clean_text[:1000] + "..."
            content_parts.append(f"Content: {clean_text}")
        
        combined_text = "\n".join(content_parts)
        
        # Format existing questions
        existing_text = "\n".join([f"- {q}" for q in existing_questions[:5]])
        
        prompt = f"""
        Based on the following educational content, create {num_questions} NEW multiple-choice questions that are DIFFERENT from the existing questions.

        Content:
        {combined_text}

        EXISTING QUESTIONS (DO NOT REPEAT THESE):
        {existing_text}

        Return ONLY a valid JSON object with this structure. No other text.
        
        {{
            "questions": [
                {{
                    "text": "Question text",
                    "options": {{
                        "A": "Option A",
                        "B": "Option B",
                        "C": "Option C",
                        "D": "Option D"
                    }},
                    "correct_answer": "A",
                    "explanation": "Brief explanation"
                }}
            ]
        }}
        """
        
        # Try models in order
        models_to_try = [
            'models/gemini-2.5-flash',
            'models/gemini-flash-latest',
            'models/gemini-2.5-pro',
        ]
        
        last_error = None
        quota_error = False
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                
                content = response.text
                content = re.sub(r'```json\s*', '', content)
                content = re.sub(r'```\s*', '', content)
                content = content.strip()
                
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    quiz_data = json.loads(json_str)
                else:
                    quiz_data = json.loads(content)
                
                if 'questions' in quiz_data and quiz_data['questions']:
                    # Validate questions
                    validated = []
                    for q in quiz_data['questions'][:num_questions]:
                        if all(k in q for k in ['text', 'options', 'correct_answer']):
                            validated.append(q)
                    
                    if validated:
                        result = {
                            'success': True,
                            'questions': validated
                        }
                        # Cache for 1 hour
                        cache.set(cache_key, result, timeout=3600)
                        return result
                
            except Exception as e:
                error_str = str(e)
                last_error = error_str
                if '429' in error_str or 'quota' in error_str.lower():
                    quota_error = True
                continue
        
        if quota_error:
            return {'success': False, 'error': 'Daily API limit reached. Please try again tomorrow.', 'quota_error': True}
        else:
            return {'success': False, 'error': f'Failed to generate questions. Last error: {last_error}'}