import gradio as gr
import os
from google import genai
from google.genai import types
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

SYSTEM_PROMPT = """You are an expert photo editor. Generate an image based on the provided photo. 
Change ONLY the hairstyle. Keep the face, skin tone, expression, clothes, pose, background and lighting exactly the same. 
The new hairstyle should be: {hairstyle}. 
Realistic photo, natural skin and hair texture, 3:4 portrait."""

# ==========================================
# 2. ЛОГИКА ГЕНЕРАЦИИ
# ==========================================
def change_hair(photo, selected_style, custom_style):
    if not photo:
        return None, "❌ Ошибка: Загрузите фото"
    
    try:
        from google.genai import types
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None, "❌ Ошибка конфигурации сервера: API-ключ не найден"
        
        proxy_url = "https://gemini-proxy.vv-molodec.workers.dev"
        
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

        # ИСПОЛЬЗУЕМ ПРАВИЛЬНОЕ ИМЯ МОДЕЛИ И УКАЗЫВАЕМ, ЧТО НУЖНА КАРТИНКА
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt_text, photo],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )
        
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if isinstance(image_bytes, str):
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
        with gr.Column():
            # Поле для ввода ключа УБРАНО
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
            
        with gr.Column():
            output_image = gr.Image(label="Результат")
            output_text = gr.Textbox(label="Статус")
            
    btn.click(
        fn=change_hair, 
        inputs=[photo_input, style_dropdown, custom_input], # Убрали api_key_input
        outputs=[output_image, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
