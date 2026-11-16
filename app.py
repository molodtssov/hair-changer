import gradio as gr
import os
import requests
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

SYSTEM_PROMPT_TEXT = """You are an expert photo editor. Generate an image based on the provided photo. 
Change ONLY the hairstyle. Keep the face, skin tone, expression, clothes, pose, background and lighting exactly the same. 
The new hairstyle should be: {hairstyle}. 
Realistic photo, natural skin and hair texture, 3:4 portrait."""

# ==========================================
# 2. ЛОГИКА ГЕНЕРАЦИИ
# ==========================================
def change_hair(photo, ref_photo, selected_style, custom_style):
    if not photo:
        return None, "❌ Ошибка: Загрузите ваше фото"
    
    try:
        account_id = os.getenv("CF_ACCOUNT_ID")
        api_token = os.getenv("CF_API_TOKEN")
        
        if not account_id or not api_token:
            return None, "❌ Ошибка конфигурации сервера: добавьте CF_ACCOUNT_ID и CF_API_TOKEN в Render"

        # Конвертируем фото пользователя
        buffered = io.BytesIO()
        photo.save(buffered, format="JPEG")
        image_bytes = buffered.getvalue()
        
        # Формируем файлы для отправки
        files = {
            "input_image_0": ("person.jpg", image_bytes, "image/jpeg")
        }

        # Проверяем, загрузил ли пользователь референс прически
        if ref_photo is not None:
            # Если загрузил, отправляем второе фото и просим взять прическу с него
            buffered_ref = io.BytesIO()
            ref_photo.save(buffered_ref, format="JPEG")
            files["input_image_1"] = ("style.jpg", buffered_ref.getvalue(), "image/jpeg")
            
            prompt_text = (
                "Change the hairstyle of the person in the first image to match the hairstyle in the second image. "
                "Keep the face, skin tone, expression, clothes, pose, background and lighting from the first image exactly the same. "
                "Realistic photo, natural hair texture."
            )
        else:
            # Если референса нет, используем текстовое описание
            if custom_style and custom_style.strip():
                prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=custom_style)
            elif selected_style:
                eng_prompt = HAIRSTYLES.get(selected_style, "a modern haircut")
                prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=eng_prompt)
            else:
                return None, "❌ Ошибка: Выберите прическу, напишите свой вариант или загрузите фото-референс"

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-2-klein-9b"
        headers = {"Authorization": f"Bearer {api_token}"}
        
        data = {"prompt": prompt_text}
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
        
        if response.status_code != 200:
            return None, f"❌ Ошибка Cloudflare ({response.status_code}): {response.text}"

        response_json = response.json()
        if not response_json.get("success"):
            return None, f"❌ Ошибка Cloudflare: {response_json.get('errors')}"
            
        image_result = response_json["result"]["image"]
        
        # Обработка результата (ссылка или base64)
        if image_result.startswith("http"):
            img_response = requests.get(image_result, timeout=30)
            result_image = Image.open(io.BytesIO(img_response.content))
        else:
            if image_result.startswith("data:image"):
                image_result = image_result.split(",")[1]
            image_bytes = base64.b64decode(image_result)
            result_image = Image.open(io.BytesIO(image_bytes))
        
        return result_image, "✅ Готово! Ваша новая прическа."

    except Exception as e:
        return None, f"❌ Ошибка API: {str(e)}"

# ==========================================
# 3. ИНТЕРФЕЙС GRADIO
# ==========================================
with gr.Blocks(title="AI Подбор Прически") as demo:
    gr.Markdown("# 💇‍♀️ AI Подбор Прически")
    gr.Markdown("Загрузите ваше фото. Вы можете выбрать готовый стиль, написать пожелание словами **ИЛИ** загрузить фото прически-референса (тогда стиль возьмется с него).")
    
    with gr.Row():
        with gr.Column():
            photo_input = gr.Image(type="pil", label="Ваше фото (обязательно)")
            
            ref_photo_input = gr.Image(type="pil", label="Фото прически-референса (опционально)")
            
            gr.Markdown("--- ИЛИ выберите стиль ниже ---")
            
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
        inputs=[photo_input, ref_photo_input, style_dropdown, custom_input], 
        outputs=[output_image, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
