import base64
import logging
from io import BytesIO
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
from PIL import Image

logger = logging.getLogger(__name__)


def index(request):
    return render(request, 'notes/index.html')


@csrf_exempt
def generate_summary(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']

        try:
            # Проверяем и обрабатываем изображение
            image = Image.open(image_file)

            # Уменьшаем изображение если оно слишком большое (макс 1024px)
            max_size = 1024
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size))

            # Конвертируем в JPEG для совместимости
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Сохраняем в буфер и кодируем в base64
            buffered = BytesIO()
            image.save(buffered, format='JPEG', quality=85)
            image_data = base64.b64encode(buffered.getvalue()).decode('utf-8')

            logger.info(f"Изображение обработано: {image.size}, размер base64: {len(image_data)} байт")

            # Инициализируем клиент OpenRouter
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.OPENROUTER_API_KEY,
            )

            # Пробуем несколько моделей по очереди
            models_to_try = [
                "inclusionai/ling-3.0-flash-vl:free",
                "google/gemma-3-12b-it:free",
            ]

            last_error = None

            for model in models_to_try:
                try:
                    logger.info(f"Пробуем модель: {model}")

                    completion = client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "Ты помощник для создания конспектов. Анализируй изображения с текстом и создавай структурированные конспекты на русском языке."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Проанализируй это изображение и сделай краткий конспект текста. Выдели:\n• Основные идеи\n• Ключевые моменты\n• Важные детали\n\nОтвет дай на русском языке в структурированном виде."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{image_data}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=1000,
                        temperature=0.7
                    )

                    summary = completion.choices[0].message.content
                    logger.info(f"Успешно сгенерировано с моделью {model}")

                    return JsonResponse({
                        'success': True,
                        'summary': summary,
                        'model_used': model
                    })

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Модель {model} не сработала: {e}")
                    continue

            # Если все модели не сработали
            return JsonResponse({
                'success': False,
                'error': f'Все модели не сработали. Последняя ошибка: {last_error}'
            }, status=500)

        except Exception as e:
            logger.error(f"Ошибка обработки: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'No image uploaded'}, status=400)