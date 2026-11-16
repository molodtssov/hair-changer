import gradio as gr
import os
import requests
from PIL import Image
import io
import base64
import time

# ==========================================
# 1. КАТАЛОГ ПРИЧЕСОК (Визуальная галерея)
# ==========================================
# Стабильные картинки с Pexels (можно заменить на свои)
HAIRSTYLE_GALLERY = [
    ("Боб-каре", "https://images.pexels.com/photos/3993449/pexels-photo-3993449.jpeg?auto=compress&cs=tinysrgb&w=600", "a classic short bob haircut with straight bangs, sleek and shiny"),
    ("Кудри", "https://images.pexels.com/photos/3993398/pexels-photo-3993398.jpeg?auto=compress&cs=tinysrgb&w=600", "natural curly hair, defined and bouncy curls"),
    ("Блонд", "https://images.pexels.com/photos/3993467/pexels-photo-3993467.jpeg?auto=compress&cs=tinysrgb&w=600", "platinum blonde bleached hair, icy tone"),
    ("Андеркат", "https://images.pexels.com/photos/1319460/pexels-photo-1319460.jpeg?auto=compress&cs=tinysrgb&w=600", "a cool haircut with shaved sides and long hair on top (undercut)")
]

SYSTEM_PROMPT_TEXT = """You are an expert photo editor. Generate an image based on the provided photo. 
Change ONLY the hairstyle. Keep the face, skin tone, expression, clothes, pose, background and lighting exactly the same. 
The new hairstyle should be: {hairstyle}. 
Realistic photo, natural skin and hair texture, 3:4 portrait."""

# ==========================================
# 2. ОБЩАЯ ЛОГИКА ГЕНЕРАЦИИ
# ==========================================
def process_generation(photo, prompt_text, style_name_display):
    if not photo:
        return None, "❌ Ошибка: Загрузите ваше фото"
    
    try:
        account_id = os.getenv("CF_ACCOUNT_ID")
        api_token = os.getenv("CF_API_TOKEN")
        
        if not account_id or not api_token:
            return None, "❌ Ошибка конфигурации сервера"

        def resize_image(img):
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            return buffered.getvalue()

        image_bytes = resize_image(photo)
        files = {"input_image_0": ("person.jpg", image_bytes, "image/jpeg")}
        data = {"prompt": prompt_text}

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-2-klein-9b"
        headers = {"Authorization": f"Bearer {api_token}"}

        last_error = None
        for attempt in range(3):
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            
            if response.status_code == 200:
                response_json = response.json()
                if response_json.get("success"):
                    image_result = response_json["result"]["image"]
                    if image_result.startswith("http"):
                        img_response = requests.get(image_result, timeout=30)
                        return Image.open(io.BytesIO(img_response.content)), f"✅ Готово! {style_name_display}"
                    else:
                        if image_result.startswith("data:image"):
                            image_result = image_result.split(",")[1]
                        return Image.open(io.BytesIO(base64.b64decode(image_result))), f"✅ Готово! {style_name_display}"
            
            if response.status_code == 500:
                last_error = response.text
                time.sleep(2) 
                continue
            else:
                break

        return None, "⚠️ Сервер Cloudflare перегружен. Нажмите еще раз."

    except Exception as e:
        return None, f"❌ Ошибка API: {str(e)}"

# --- Функции-обертки ---
def process_from_gallery(photo, style_name):
    if not style_name: return None, "Выберите прическу"
    eng_prompt = next((item[2] for item in HAIRSTYLE_GALLERY if item[0] == style_name), "a modern haircut")
    prompt = SYSTEM_PROMPT_TEXT.format(hairstyle=eng_prompt)
    return process_generation(photo, prompt, f"Прическа: {style_name}")

def process_from_text(photo, custom_text):
    if not custom_text: return None, "Введите описание прически"
    prompt = SYSTEM_PROMPT_TEXT.format(hairstyle=custom_text)
    return process_generation(photo, prompt, "Ваш текстовый запрос")

# ==========================================
# 3. ИНТЕРФЕЙС GRADIO
# ==========================================
with gr.Blocks(title="AI Подбор Прически") as demo:
    gr.Markdown("# 💇‍♀️ AI Подбор Прически")
    
    with gr.Row():
        with gr.Column(scale=1):
            photo_input = gr.Image(type="pil", label="1. Загрузите ваше фото")
            
        with gr.Column(scale=1):
            with gr.Tabs():
                with gr.Tab("🎨 Каталог"):
                    gallery_data = [[item[1], item[0]] for item in HAIRSTYLE_GALLERY]
                    style_gallery = gr.Gallery(
                        value=gallery_data, label="Кликните на прическу, чтобы примерить", 
                        allow_preview=False, columns=2, rows=2, height=300
                    )
                    selected_gallery_style = gr.Textbox(visible=False)
                    
                with gr.Tab("✍️ Свой текст"):
                    custom_input = gr.Textbox(label="Опишите прическу", placeholder="Например: короткая стрижка с синими кончиками")
                    btn_text = gr.Button("✨ Сгенерировать по тексту", variant="primary")

    with gr.Row():
        output_image = gr.Image(label="Результат")
        output_text = gr.Textbox(label="Статус")

    def on_gallery_select(evt: gr.SelectData):
        return evt.value[1] 

    style_gallery.select(on_gallery_select, None, selected_gallery_style)
    
    selected_gallery_style.change(
        fn=process_from_gallery, 
        inputs=[photo_input, selected_gallery_style], 
        outputs=[output_image, output_text]
    )
    
    btn_text.click(
        fn=process_from_text,
        inputs=[photo_input, custom_input],
        outputs=[output_image, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
