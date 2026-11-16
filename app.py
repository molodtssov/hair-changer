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
# Ссылки на картинки (можно заменить на свои)
HAIRSTYLE_GALLERY = [
    ("Боб-каре", "https://images.unsplash.com/photo-1595476108010-b4d1f102b1b1?q=80&w=400&auto=format&fit=crop", "a classic short bob haircut with straight bangs, sleek and shiny"),
    ("Кудри", "https://images.unsplash.com/photo-1580618672591-eb180b1a973f?q=80&w=400&auto=format&fit=crop", "natural curly hair, defined and bouncy curls"),
    ("Блонд", "https://images.unsplash.com/photo-1522337660859-02fbefca4702?q=80&w=400&auto=format&fit=crop", "platinum blonde bleached hair, icy tone"),
    ("Андеркат", "https://images.unsplash.com/photo-1622286342621-4bd786c2447c?q=80&w=400&auto=format&fit=crop", "a cool haircut with shaved sides and long hair on top (undercut)")
]

SYSTEM_PROMPT_TEXT = """You are an expert photo editor. Generate an image based on the provided photo. 
Change ONLY the hairstyle. Keep the face, skin tone, expression, clothes, pose, background and lighting exactly the same. 
The new hairstyle should be: {hairstyle}. 
Realistic photo, natural skin and hair texture, 3:4 portrait."""

# ==========================================
# 2. ЛОГИКА ГЕНЕРАЦИИ
# ==========================================
def change_hair(photo, selected_style_name):
    if not photo:
        return None, "❌ Ошибка: Загрузите ваше фото"
    if not selected_style_name:
        return None, "❌ Ошибка: Выберите прическу из каталога"
    
    try:
        account_id = os.getenv("CF_ACCOUNT_ID")
        api_token = os.getenv("CF_API_TOKEN")
        
        if not account_id or not api_token:
            return None, "❌ Ошибка конфигурации сервера: добавьте CF_ACCOUNT_ID и CF_API_TOKEN в Render"

        # Ищем английский промпт по выбранному названию
        eng_prompt = next((item[2] for item in HAIRSTYLE_GALLERY if item[0] == selected_style_name), "a modern haircut")
        prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=eng_prompt)

        # Уменьшаем фото до 512x512
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

        # 3 попытки при ошибке 500
        last_error = None
        for attempt in range(3):
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            
            if response.status_code == 200:
                response_json = response.json()
                if response_json.get("success"):
                    image_result = response_json["result"]["image"]
                    if image_result.startswith("http"):
                        img_response = requests.get(image_result, timeout=30)
                        return Image.open(io.BytesIO(img_response.content)), f"✅ Готово! Примерена прическа: {selected_style_name}"
                    else:
                        if image_result.startswith("data:image"):
                            image_result = image_result.split(",")[1]
                        return Image.open(io.BytesIO(base64.b64decode(image_result))), f"✅ Готово! Примерена прическа: {selected_style_name}"
            
            if response.status_code == 500:
                last_error = response.text
                time.sleep(2) 
                continue
            else:
                break

        return None, f"⚠️ Сервер Cloudflare перегружен. Нажмите еще раз через пару секунд."

    except Exception as e:
        return None, f"❌ Ошибка API: {str(e)}"

# ==========================================
# 3. ИНТЕРФЕЙС GRADIO (С галереей)
# ==========================================
with gr.Blocks(title="AI Подбор Прически") as demo:
    gr.Markdown("# 💇‍♀️ AI Подбор Прически (Sims-style)")
    gr.Markdown("Загрузите ваше фото, затем кликните на понравившуюся прическу в каталоге ниже, чтобы примерить её.")
    
    with gr.Row():
        with gr.Column():
            photo_input = gr.Image(type="pil", label="1. Загрузите ваше фото")
            
            # Создаем галерею из картинок
            gallery_data = [[item[1], item[0]] for item in HAIRSTYLE_GALLERY]
            
            style_gallery = gr.Gallery(
                value=gallery_data, 
                label="2. Кликните на прическу, чтобы примерить", 
                allow_preview=False,
                columns=2,
                rows=2,
                height=400
            )
            
        with gr.Column():
            output_image = gr.Image(label="Результат")
            output_text = gr.Textbox(label="Статус")
            
    # При клике на картинку в галерее, передаем её название в функцию
    def on_gallery_select(evt: gr.SelectData):
        # evt.value возвращает кортеж (путь_к_картинке, подпись)
        # Нам нужна подпись (название прически)
        return evt.value[1]

    # Скрытое текстовое поле для хранения выбранного стиля
    selected_style_hidden = gr.Textbox(visible=False)

    style_gallery.select(on_gallery_select, None, selected_style_hidden)
    selected_style_hidden.change(
        fn=change_hair, 
        inputs=[photo_input, selected_style_hidden], 
        outputs=[output_image, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
