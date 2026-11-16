import gradio as gr
import os
import requests
from PIL import Image, ImageOps
import io
import base64
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 1. КАТАЛОГ ПРИЧЕСОК
# ==========================================
HAIRSTYLES = {
    # Женские
    "Боб-каре": "a classic short bob haircut with straight bangs, sleek and shiny",
    "Удлиненный боб (Lob)": "a long bob (lob) haircut, collarbone length, soft waves",
    "Каскад": "a cascading layered haircut, long layers, voluminous",
    "Пикси": "a trendy pixie cut, very short, textured and edgy",
    "Длинные волны": "long flowing wavy hair, voluminous and romantic",
    "Кудри": "natural curly hair, defined and bouncy curls",
    "Высокий хвост": "sleek high ponytail, smooth and elegant",
    "Пучок (Bun)": "a neat top knot bun, elegant and modern",
    "Челка-шторка": "long curtain bangs, parted in the middle",
    "Прямой пробор": "perfectly straight hair with a middle part",
    # Мужские
    "Кроп": "a short textured crop haircut, modern and masculine",
    "Фейд (Fade)": "a low skin fade, clean and sharp",
    "Помпадур": "a classic pompadour haircut, slicked back with volume on top",
    "Квифф": "a textured quiff haircut, modern and stylish",
    "Андеркат": "shaved sides with long hair on top (undercut)",
    "Мужской пучок": "a stylish man bun, long hair tied at the back",
    "Ирокез": "a faux hawk mohawk, edgy and modern",
    # Цвета
    "Блонд": "platinum blonde bleached hair, icy tone",
    "Пепельный блонд": "ash blonde hair color, cool and sophisticated",
    "Рыжий": "vibrant copper red hair, rich and glossy",
    "Розовые кончики": "pink dyed hair tips, trendy and fun",
    "Синий цвет": "vibrant blue dyed hair, bold and striking",
    "Камуфляж седины": "natural gray coverage, subtle blended hair color",
}

SYSTEM_PROMPT = """Edit the provided photo. Change ONLY the hairstyle to: {hairstyle}.

CRITICAL RULES:
- Keep the person's face, facial features, skin tone, expression EXACTLY as in the original
- Keep the same clothing, pose, body proportions, background and lighting
- The result must look like the SAME person, just with a different hairstyle
- Realistic photo, natural hair texture, seamless blending at hairline
- 3:4 portrait format"""

CF_MODEL = "@cf/black-forest-labs/flux-2-klein-9b"
MAX_RETRIES = 3
RETRY_DELAY = 2


# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def prepare_image(img: Image.Image, max_size: int = 512) -> bytes:
    """EXIF-ориентация, конвертация RGBA→RGB, ресайз, JPEG."""
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def parse_response(resp_json: dict) -> Image.Image:
    """Извлекает изображение из ответа API (base64 или URL)."""
    image_data = resp_json["result"]["image"]
    if image_data.startswith("http"):
        r = requests.get(image_data, timeout=30)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content))
    if image_data.startswith("data:image"):
        image_data = image_data.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(image_data)))


# ==========================================
# 3. ЛОГИКА ГЕНЕРАЦИИ
# ==========================================
def change_hair(photo, reference_photo, selected_style, custom_style):
    if photo is None:
        return None, "❌ Загрузите ваше фото"

    account_id = os.getenv("CF_ACCOUNT_ID")
    api_token = os.getenv("CF_API_TOKEN")
    if not account_id or not api_token:
        return None, "❌ Ошибка конфигурации сервера"

    # Определяем стиль
    if custom_style and custom_style.strip():
        hairstyle = custom_style.strip()
        display_name = "Ваш вариант"
    elif selected_style:
        hairstyle = HAIRSTYLES.get(selected_style, "a modern haircut")
        display_name = selected_style
    else:
        return None, "❌ Выберите причёску или опишите свой вариант"

    prompt = SYSTEM_PROMPT.format(hairstyle=hairstyle)

    # Собираем multipart: основное фото + опциональный референс
    files = {
        "input_image_0": ("person.jpg", prepare_image(photo), "image/jpeg"),
    }
    if reference_photo is not None:
        files["input_image_1"] = ("reference.jpg", prepare_image(reference_photo), "image/jpeg")
        prompt += "\nUse the second image as a hairstyle reference. Apply that hairstyle to the person in the first image."

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{CF_MODEL}"
    headers = {"Authorization": f"Bearer {api_token}"}

    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Attempt {attempt + 1}/{MAX_RETRIES}: {display_name}")
            resp = requests.post(
                url, headers=headers,
                files=files, data={"prompt": prompt},
                timeout=120,
            )

            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    img = parse_response(result)
                    return img, f"✅ Готово! {display_name}"
                else:
                    last_error = str(result.get("errors", "Unknown error"))
                    logger.warning(f"API error: {last_error}")

            elif resp.status_code in (429, 500, 502, 503):
                last_error = f"HTTP {resp.status_code}"
                logger.warning(f"Retryable error: {last_error}")
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            else:
                last_error = resp.text[:200]
                logger.error(f"Non-retryable error: {last_error}")
                break

        except requests.exceptions.Timeout:
            last_error = "Timeout"
            logger.warning("Request timed out")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            last_error = str(e)
            logger.error(f"Unexpected error: {e}")
            break

    return None, f"⚠️ Не удалось сгенерировать ({last_error}). Попробуйте ещё раз."


# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================
custom_css = """
.gradio-container {
    max-width: 1100px !important;
    margin: 0 auto !important;
}
#header-text { text-align: center; margin-bottom: 1.5rem; }
#header-text h1 {
    font-weight: 800; font-size: 2.2rem;
    background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
"""

theme = gr.themes.Soft(
    primary_hue="rose", secondary_hue="teal", neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui"],
)

with gr.Blocks(title="AI Подбор Причёски", theme=theme, css=custom_css) as demo:
    with gr.Column(elem_id="header-text"):
        gr.HTML("""
            <h1>💇 AI Стилист</h1>
            <p>Загрузите фото и примерьте новый образ</p>
        """)

    with gr.Row():
        with gr.Column(scale=1):
            photo_input = gr.Image(type="pil", label="📸 Ваше фото (обязательно)")
            ref_input = gr.Image(type="pil", label="💇 Фото причёски-референса (опционально)")

            gr.Markdown("---\n**ИЛИ** выберите стиль ниже:")
            style_dropdown = gr.Dropdown(
                choices=list(HAIRSTYLES.keys()),
                label="Готовые стили",
                value=None,
                info="Выберите из списка или напишите свой вариант ниже",
            )
            custom_input = gr.Textbox(
                label="Или опишите свой вариант",
                placeholder="Например: пепельный блонд с чёлкой",
            )
            btn = gr.Button("✨ Сгенерировать", variant="primary", size="lg")

        with gr.Column(scale=1):
            output_image = gr.Image(label="Результат", interactive=False)
            output_text = gr.Textbox(label="Статус", interactive=False)

    btn.click(
        fn=change_hair,
        inputs=[photo_input, ref_input, style_dropdown, custom_input],
        outputs=[output_image, output_text],
    )

# Очередь: максимум 2 одновременных запроса
demo.queue(max_size=20, default_concurrency_limit=2)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=8080)
