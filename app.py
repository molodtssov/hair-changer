import gradio as gr
import os
from google import genai
from PIL import Image
import io
import base64

# ==========================================
# 1. СЛОВАРЬ ПРИЧЕСОК (Русский -> Английский)
# ==========================================
HAIRSTYLES = {
    "Боб-каре (Короткое)": "a classic short bob haircut with straight bangs, sleek and shiny",
    "Длинные волны": "long flowing wavy hair, voluminous and romantic style",
    "Пикси (Очень короткая)": "a trendy pixie cut, very short, textured and edgy",
    "Короткая стрижка (Кроп)": "a short textured crop haircut, modern and masculine style",
    "Стрижка с выбритыми висками": "a cool haircut with shaved sides and long hair on top (undercut)",
    "Кудри": "natural curly hair, defined and bouncy curls",
    "Красный цвет": "vibrant red hair color, dyed and glossy",
    "Блонд (Обесцвечивание)": "platinum blonde bleached hair, icy tone"
}

# Системный промпт: строгое указание менять только волосы
SYSTEM_PROMPT = """You are an expert photo editor. Generate an image based on the provided photo. 
Change ONLY the hairstyle. Keep the face, skin tone, expression, clothes, pose, background and lighting exactly the same. 
The new hairstyle should be: {hairstyle}. 
Realistic photo, natural skin and hair texture, 3:4 portrait."""

# ==========================================
# 2. ЛОГИКА ГЕНЕРАЦИИ
# ==========================================
def change_hair(api_key, photo, selected_style, custom_style):
    if not api_key:
        return None, "❌ Ошибка: Введите API-ключ Gemini"
    if not photo:
        return None, "❌ Ошибка: Загрузите фото"
    
    try:
        from google.genai import types
        
        # ВАШ URL ПРОКСИ ИЗ CLOUDFLARE
        proxy_url = "https://gemini-proxy.vv-molodec.workers.dev"
        
        # Правильная передача базового URL для прокси в новом SDK
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(base_url=proxy_url)
        )
        
        if custom_style and custom_style.strip():
            prompt_text = SYSTEM_PROMPT.format(hairstyle=custom_style)
        elif selected_style:
            eng_prompt = HAIRSTYLES.get(selected_style, "a modern haircut")
            prompt_text = SYSTEM_PROMPT.format(hairstyle=eng_prompt)
        else:
            return None, "❌ Ошибка: Выберите прическу или напишите свой вариант"

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[prompt_text, photo]
        )
        
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if isinstance(image_bytes, str):
                    import base64
                    image_bytes = base64.b64decode(image_bytes)
                result_image = Image.open(io.BytesIO(image_bytes))
                return result_image, "✅ Готово! Ваша новая прическа."
                
        return None, "⚠️ Нейросеть не смогла сгенерировать фото. Попробуйте изменить описание."

    except Exception as e:
        return None, f"❌ Ошибка API: {str(e)}"

# ==========================================
# 3. ИНТЕРФЕЙС GRADIO
# ==========================================
with gr.Blocks(title="AI Подбор Прически") as demo:
    gr.Markdown("# 💇‍♀️ AI Подбор Прически")
    gr.Markdown("Загрузите фото и выберите желаемый образ. Вы можете выбрать готовый стиль или написать свой вариант на русском языке.")
    
    with gr.Row():
        # Левая колонка (Ввод данных)
        with gr.Column():
            api_key_input = gr.Textbox(
                label="Google Gemini API Key", 
                type="password",
                placeholder="Вставьте ваш ключ от Google AI Studio"
            )
            
            photo_input = gr.Image(type="pil", label="Ваше фото")
            
            style_dropdown = gr.Dropdown(
                choices=list(HAIRSTYLES.keys()), 
                label="Выберите прическу (готовый стиль)", 
                value="Боб-каре (Короткое)"
            )
            
            custom_input = gr.Textbox(
                label="Или опишите свой вариант (на русском)", 
                placeholder="Например: короткая стрижка с челкой и синим цветом"
            )
            
            btn = gr.Button("✨ Сгенерировать", variant="primary")
            
        # Правая колонка (Результат)
        with gr.Column():
            output_image = gr.Image(label="Результат")
            output_text = gr.Textbox(label="Статус")
            
    # Привязка кнопки к функции
    btn.click(
        fn=change_hair, 
        inputs=[api_key_input, photo_input, style_dropdown, custom_input], 
        outputs=[output_image, output_text]
    )

# Запуск приложения (ВАЖНО для Cloud Run)
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
