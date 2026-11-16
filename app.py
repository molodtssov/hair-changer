import gradio as gr
import os
import requests
from PIL import Image
import io
import base64
import time

# ==========================================
# 1. БОЛЬШОЙ КАТАЛОГ ПРИЧЕСОК
# ==========================================
HAIRSTYLES = {
    # --- Женские стрижки и укладки ---
    "Боб-каре (Короткое)": "a classic short bob haircut with straight bangs, sleek and shiny",
    "Удлиненный боб (Lob)": "a long bob (lob) haircut, collarbone length, soft waves",
    "Каскад": "a cascading layered haircut, long layers, voluminous",
    "Пикси (Очень короткая)": "a trendy pixie cut, very short, textured and edgy",
    "Длинные волны": "long flowing wavy hair, voluminous and romantic style",
    "Кудри": "natural curly hair, defined and bouncy curls",
    "Высокий хвост": "sleek high ponytail, smooth and elegant",
    "Пучок (Bun)": "a neat top knot bun, elegant and modern",
    "Челка-шторка": "long curtain bangs, parted in the middle",
    "Прямой пробор": "perfectly straight hair with a middle part",
    
    # --- Мужские стрижки ---
    "Кроп (Текстурированный)": "a short textured crop haircut, modern and masculine style",
    "Фейд (Fade)": "a low skin fade, clean and sharp",
    "Помпадур": "a classic pompadour haircut, slicked back with volume on top",
    "Квифф": "a textured quiff haircut, modern and stylish",
    "Андеркат (Выбритые виски)": "a cool haircut with shaved sides and long hair on top (undercut)",
    "Мужской пучок (Man Bun)": "a stylish man bun, long hair tied at the back",
    "Ирокез": "a faux hawk mohawk, edgy and modern",
    
    # --- Цвета и окрашивание ---
    "Блонд (Обесцвечивание)": "platinum blonde bleached hair, icy tone",
    "Пепельный блонд": "ash blonde hair color, cool and sophisticated",
    "Красный (Рыжий)": "vibrant copper red hair, rich and glossy",
    "Розовые кончики": "pink dyed hair tips, trendy and fun",
    "Синий цвет": "vibrant blue dyed hair, bold and striking",
    "Камуфляж седины": "natural gray coverage, subtle and blended hair color"
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
            return None, "❌ Ошибка конфигурации сервера"

        # Сжимаем фото
        def resize_image(img):
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            return buffered.getvalue()

        image_bytes = resize_image(photo)
        files = {"input_image_0": ("person.jpg", image_bytes, "image/jpeg")}
        
        if custom_style and custom_style.strip():
            prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=custom_style)
            display_name = "Ваш текстовый запрос"
        elif selected_style:
            eng_prompt = HAIRSTYLES.get(selected_style, "a modern haircut")
            prompt_text = SYSTEM_PROMPT_TEXT.format(hairstyle=eng_prompt)
            display_name = selected_style
        else:
            return None, "❌ Ошибка: Выберите прическу или напишите свой вариант"

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

        return None, f"⚠️ Сервер перегружен. Попробуйте еще раз."

    except Exception as e:
        return None, f"❌ Ошибка: {str(e)}"


# ==========================================
# 3. ДИЗАЙН И ИНТЕРФЕЙС
# ==========================================
custom_css = """
.gradio-container {
    max-width: 1000px !important;
    margin: 0 auto !important;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
#header-text {
    text-align: center;
    margin-bottom: 2rem;
    color: #1a1a1a;
}
#header-text h1 {
    font-weight: 800;
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
    background: -webkit-linear-gradient(45deg, #FF6B6B, #4ECDC4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
#header-text p {
    color: #666;
    font-size: 1.1rem;
}
"""

theme = gr.themes.Soft(
    primary_hue="rose",
    secondary_hue="teal",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]
)

with gr.Blocks(title="AI Подбор Прически", theme=theme, css=custom_css) as demo:
    
    with gr.Column(elem_id="header-text"):
        gr.HTML("""
            <h1>💇‍♀️ AI Стилист</h1>
            <p>Загрузите фото и примерьте новый образ за 10 секунд</p>
        """)
    
    with gr.Row():
        with gr.Column(scale=1):
            photo_input = gr.Image(type="pil", label="Ваше фото", elem_classes="photo-box")
            
            gr.Markdown("### Выберите образ")
            
            # Теперь здесь 23 стиля!
            style_dropdown = gr.Dropdown(
                choices=list(HAIRSTYLES.keys()), 
                label="Готовые стили (можно листать)", 
                value="Боб-каре (Короткое)",
                info="Выберите вариант из списка или напишите свой ниже"
            )
            
            custom_input = gr.Textbox(
                label="Или опишите свой вариант", 
                placeholder="Например: пепельный блонд с челкой"
            )
            
            btn = gr.Button("✨ Сгенерировать", variant="primary", size="lg")
            
        with gr.Column(scale=1):
            output_image = gr.Image(label="Результат", interactive=False)
            output_text = gr.Textbox(label="Статус", interactive=False)
            
    btn.click(
        fn=change_hair, 
        inputs=[photo_input, style_dropdown, custom_input], 
        outputs=[output_image, output_text]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
