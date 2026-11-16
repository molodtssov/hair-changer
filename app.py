import gradio as gr
import os
import requests
from PIL import Image
import io
import base64

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

def change_hair(photo, selected_style, custom_style):
    if not photo:
        return None, "❌ Ошибка: Загрузите фото"
    
    try:
        account_id = os.getenv("CF_ACCOUNT_ID")
        api_token = os.getenv("CF_API_TOKEN")
        
        if not account_id or not api_token:
            return None, "❌ Ошибка конфигурации сервера: добавьте CF_ACCOUNT_ID и CF_API_TOKEN в Render"

        if custom_style and custom_style.strip():
            prompt_text = SYSTEM_PROMPT.format(hairstyle=custom_style)
        elif selected_style:
            eng_prompt = HAIRSTYLES.get(selected_style, "a modern haircut")
            prompt_text = SYSTEM_PROMPT.format(hairstyle=eng_prompt)
        else:
            return None, "❌ Ошибка: Выберите прическу или напишите свой вариант"

        # Конвертируем фото в байты
        buffered = io.BytesIO()
        photo.save(buffered, format="JPEG")
        image_bytes = buffered.getvalue()

        # Используем новую модель FLUX.2 [klein] 9B
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-2-klein-9b"
        headers = {"Authorization": f"Bearer {api_token}"}
        
        # Эта модель ожидает multipart/form-data
        files = {
            "input_image_0": ("input.jpg", image_bytes, "image/jpeg")
        }
        data = {"prompt": prompt_text}
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
        
        # Если ответ не 200, показываем детали ошибки от Cloudflare
        if response.status_code != 200:
            error_detail = response.text
            return None, f"❌ Ошибка Cloudflare ({response.status_code}): {error_detail}"

        # Cloudflare возвращает JSON с ссылкой на изображение
        response_json = response.json()
        if not response_json.get("success"):
            return None, f"❌ Ошибка Cloudflare: {response_json.get('errors')}"
            
        image_url = response_json["result"]["image"]
        
        # Скачиваем готовое изображение по ссылке
        img_response = requests.get(image_url, timeout=30)
        result_image = Image.open(io.BytesIO(img_response.content))
        
        return result_image, "✅ Готово! Ваша новая прическа (FLUX.2)."

    except Exception as e:
        return None, f"❌ Ошибка API: {str(e)}"
        
with gr.Blocks(title="AI Подбор Прически") as demo:
    gr.Markdown("# 💇‍♀️ AI Подбор Прически (Cloudflare Workers AI)")
    gr.Markdown("Загрузите фото и выберите желаемый образ. Вы можете выбрать готовый стиль или написать свой вариант на русском языке.")
    
    with gr.Row():
        with gr.Column():
            photo_input = gr.Image(type="pil", label="Ваше фото")
            style_dropdown = gr.Dropdown(choices=list(HAIRSTYLES.keys()), label="Выберите прическу (готовый стиль)", value="Боб-каре (Короткое)")
            custom_input = gr.Textbox(label="Или опишите свой вариант (на русском)", placeholder="Например: короткая стрижка с челкой и синим цветом")
            btn = gr.Button("✨ Сгенерировать", variant="primary")
            
        with gr.Column():
            output_image = gr.Image(label="Результат")
            output_text = gr.Textbox(label="Статус")
            
    btn.click(fn=change_hair, inputs=[photo_input, style_dropdown, custom_input], outputs=[output_image, output_text])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
