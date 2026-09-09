import flet as ft
import requests

API_BASE = "http://127.0.0.1:8000"

def main(page: ft.Page):
    page.title = "Flap"
    
    bg_color = "#1F1B18"       
    card_color = "#342D27"     
    accent_color = "#D4A373"   
    text_color = "#FAEDCD"     
    
    page.bgcolor = bg_color
    page.padding = 40
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    current_cards = []
    current_card_index = 0
    is_front = True

    # --- UI ELEMENTS ---
    deck_dropdown = ft.Dropdown(
        label="Select a Deck", 
        width=300, 
        color=text_color
    )
    
    card_text = ft.Text(
        value="Select a deck or upload a new PDF!", 
        size=24, 
        text_align=ft.TextAlign.CENTER, 
        weight=ft.FontWeight.W_400,
        color=text_color
    )
    
    progress_ring = ft.ProgressRing(visible=False, color=accent_color)
    
    card_content = ft.Column(
        [progress_ring, card_text],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )
    
    card_container = ft.Container(
        content=card_content,
        width=600,
        height=350,
        bgcolor=card_color,
        border_radius=20,
        padding=40,
        alignment=ft.Alignment(0, 0),
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=15, color="#000000"),
        on_click=lambda e: flip_card(),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
    )

    # --- ASYNC FILE PICKER SERVICE ---
    file_picker = ft.FilePicker()
    # Attach as a background service
    page.services.append(file_picker)

    async def on_upload_click(e):
        # Flet 0.84+ allows awaiting pick_files directly
        files = await file_picker.pick_files(allowed_extensions=["pdf"])
        
        if not files:
            return
            
        selected_file = files[0]
        
        card_text.value = f"Extracting text from '{selected_file.name}'...\nThis takes a moment."
        progress_ring.visible = True
        page.update()
        
        try:
            with open(selected_file.path, "rb") as f:
                pdf_data = {"file": (selected_file.name, f, "application/pdf")}
                response = requests.post(f"{API_BASE}/upload/", files=pdf_data)
            
            if response.status_code == 200:
                card_text.value = "Upload complete! Select your new deck from the dropdown above."
                load_decks() 
            else:
                card_text.value = f"Backend Error: {response.status_code} - {response.text}"
        except Exception as err:
            card_text.value = f"Upload Failed: {err}"
            
        progress_ring.visible = False
        page.update()

    # --- FUNCTIONS ---
    def load_decks():
        try:
            response = requests.get(f"{API_BASE}/decks/")
            if response.status_code == 200:
                decks = response.json().get("decks", [])
                deck_dropdown.options = [ft.dropdown.Option(text=d["name"], key=str(d["id"])) for d in decks]
                page.update()
        except requests.exceptions.ConnectionError:
            card_text.value = "Error: FastAPI backend is not running!"
            page.update()

    def fetch_cards_clicked(e):
        nonlocal current_cards, current_card_index, is_front
        deck_id = deck_dropdown.value
        
        if not deck_id:
            card_text.value = "Please select a deck first."
            page.update()
            return

        try:
            response = requests.get(f"{API_BASE}/decks/{deck_id}/cards")
            if response.status_code == 200:
                data = response.json()
                current_cards = data if isinstance(data, list) else data.get("cards", [])
                    
                if not current_cards:
                    card_text.value = "This deck is empty! Try another one."
                else:
                    current_card_index = 0
                    is_front = True
                    update_card_view()
            else:
                card_text.value = f"Backend Error: {response.status_code}"
            page.update()
        except Exception as err:
            card_text.value = f"App Error: {err}"
            page.update()

    def flip_card():
        nonlocal is_front
        if current_cards:
            is_front = not is_front
            update_card_view()

    def next_card(e):
        nonlocal current_card_index, is_front
        if current_cards and current_card_index < len(current_cards) - 1:
            current_card_index += 1
            is_front = True
            update_card_view()
            
    def prev_card(e):
        nonlocal current_card_index, is_front
        if current_cards and current_card_index > 0:
            current_card_index -= 1
            is_front = True
            update_card_view()

    def update_card_view():
        if not current_cards:
            return
        card = current_cards[current_card_index]
        card_text.value = card["front"] if is_front else card["back"]
        page.update()

    # --- BUTTON STYLING ---
    load_btn = ft.FilledButton(
        content="Load Cards", 
        on_click=fetch_cards_clicked, 
        style=ft.ButtonStyle(bgcolor=accent_color, color=bg_color)
    )
    
    upload_btn = ft.FilledButton(
        content="Upload PDF", 
        icon=ft.Icons.UPLOAD_FILE, 
        on_click=on_upload_click,
        style=ft.ButtonStyle(bgcolor="#4A4036", color=text_color)
    )

    nav_btn_style = ft.ButtonStyle(bgcolor="#4A4036", color=text_color, shape=ft.RoundedRectangleBorder(radius=10))

    controls_row = ft.Row(
        [
            ft.FilledButton(content="Previous", on_click=prev_card, icon=ft.Icons.ARROW_BACK, style=nav_btn_style),
            ft.FilledButton(content="Flip Card", on_click=lambda e: flip_card(), icon=ft.Icons.FLIP, style=nav_btn_style),
            ft.FilledButton(content="Next", on_click=next_card, icon=ft.Icons.ARROW_FORWARD, style=nav_btn_style),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15
    )

    # --- LAYOUT CONSTRUCTION ---
    page.add(
        ft.Row([deck_dropdown, load_btn, upload_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
        ft.Container(height=30),
        ft.Row([card_container], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(height=30),
        controls_row
    )

    load_decks()

ft.run(main)