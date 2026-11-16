import gradio as gr
import os
import requests
from PIL import Image
import io
import base64
import time

# ==========================================
# 1. СПИСОК ПРИЧЕСОК (Текстовый выбор)
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
def change_hair(photo, selected_style, custom_style):
    if not photo:
        return None, "❌ Ошибка: Загрузите ваше фото"
    
    try:
        account_id = os.getenv("CF_ACCOUNT_ID")
        api_token = os.getenv("CF_API_TOKEN")
        
        if not account_id or not api_token:
            return None, "❌ Ошибка конфигурации сервера: добавьте CF_ACCOUNT_ID и CF_API_TOKEN в Render"

        # Сжимаем фото (требование Cloudflare)
        def resize_image(img):
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            return buffered.getvalue()

        image_bytes = resize_image(photo)
        files = {"input_image_0": ("person.jpg", image_bytes, "image/jpeg")}
        
        # Если написан свой текст — используем его, иначе — из выпадающего списка
        if custom_style and custom_style.strip():
            prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=custom_style)
            display_name = "Ваш текстовый запрос"
        elif selected_style:
            eng_prompt = HAIRSTYLES.get(selected_style, "a modern haircut")
            prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=eng_prompt)
            display_name = selected_style
        else:
            return None, "❌ Ошибка: Выберите прическу из списка или напишите свой вариант"

        data = {"prompt": prompt_text}

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-2-klein-9b"
        headers = {"Authorization": f"Bearer {api_token}"}

        # 3 попытки при временных сбоях (ошибка 500)
        last_error = None
        for attempt in range(3):
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            
            if response.status_code == 200:
                response_json = response.json()
                if response_json.get("success"):
                    image_result = response_json["result"]["image"]
                    if image_result.startswith("http"):
                        img_response = requests.get(image_result, timeout=30)
                        return Image.open(io.BytesIO(img_response.content)), f"✅ Готово! {display_name}"
                    else:
                        if image_result.startswith("data:image"):
                            image_result = image_result.split(",")[1]
                        return Image.open(io.BytesIO(base64.b64decode(image_result))), f"✅ Готово! {display_name}"
            
            if response.status_code == 500:
                last_error = response.text
                time.sleep(2) 
                continue
            else:
                break

        # Обработка специфических ошибок
        try:
            err_json = response.json()
            errors = err_json.get("errors", [])
            if errors and errors[0].get("code") == 3030:
                return None, "⚠️ Фильтр безопасности отклонил результат. Попробуйте другое фото или другой стиль."
        except:
            pass

        return None, f"⚠️ Сервер Cloudflare временно перегружен. Нажмите «Сгенерировать» еще раз. Детали: {last_error}"

    except Exception as e:
        return None, f"❌ Ошибка API: {str(e)}"

# ==========================================
# 3. ИНТЕРФЕЙС GRADIO (Простой и надежный)
# ==========================================
with gr.Blocks(title="AI Подбор Прически") as demo:
    gr.Markdown("# 💇‍♀️ AI Подбор Прически")
    gr.Markdown("Загрузите ваше фото и выберите готовый стиль из списка **ИЛИ** напишите свое пожелание словами.")
    
    with gr.Row():
        with gr.Column():
            photo_input = gr.Image(type="pil", label="1. Загрузите ваше фото")
            
            style_dropdown = gr.Dropdown(
                choices=list(HAIRSTYLES.keys()), 
                label="2. Выберите готовый стиль", 
                value="Боб-каре (Короткое)"
            )
            
            custom_input = gr.Textbox(
                label="ИЛИ опишите свой вариант (на русском)", 
                placeholder="Например: короткая стрижка с челкой и синим цветом"
            )
            
            btn = gr.Button("✨ Сгенерировать", variant="primary")
            
        with gr.Column():
            output_image = gr.Image(label="Результат")
            output_text = gr.Textbox(label="Статус")
            
    btn.click(
        fn=change_hair, 
        inputs=[photo_input, style_dropdown, custom_input], 
        outputs=[output_image, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
