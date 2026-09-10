import flet as ft
import requests

API_BASE = "http://127.0.0.1:8000"

def main(page: ft.Page):
    page.title = "Flap - AI Study App"
    
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
    
    card_counter = ft.Text(
        value="", 
        size=14, 
        color=accent_color, 
        weight=ft.FontWeight.W_600,
        text_align=ft.TextAlign.CENTER
    )
    
    card_text = ft.Markdown(
        value="Select a deck or upload a new PDF!", 
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
    )
    
    progress_ring = ft.ProgressRing(visible=False, color=accent_color)
    
    card_content = ft.Column(
        [progress_ring, card_counter, card_text],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10
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

    # --- SLIDER UI ---
    count_label = ft.Text(value="Target Cards: 15", color=text_color, size=16)
    
    def on_slider_change(e):
        count_label.value = f"Target Cards: {int(e.control.value)}"
        page.update()

    card_slider = ft.Slider(
        min=5, max=50, divisions=9, value=15, 
        active_color=accent_color, on_change=on_slider_change, width=200
    )

    slider_container = ft.Column(
        [count_label, card_slider],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0
    )

    # --- ASYNC FILE PICKER SERVICE ---
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def on_upload_click(e):
        files = await file_picker.pick_files(allowed_extensions=["pdf"])
        if not files:
            return
            
        selected_file = files[0]
        selected_count = int(card_slider.value)
        
        card_counter.value = ""
        card_text.value = f"Extracting {selected_count} cards from '{selected_file.name}'...\nThis takes a moment."
        progress_ring.visible = True
        page.update()
        
        try:
            with open(selected_file.path, "rb") as f:
                pdf_data = {"file": (selected_file.name, f, "application/pdf")}
                upload_url = f"{API_BASE}/upload/?count={selected_count}"
                response = requests.post(upload_url, files=pdf_data)
            
            if response.status_code == 200:
                card_text.value = "Upload complete! Select your new deck from the dropdown above."
                load_decks() 
            else:
                card_text.value = f"Backend Error: {response.status_code} - {response.text}"
        except Exception as err:
            card_text.value = f"Upload Failed: {err}"
            
        progress_ring.visible = False
        page.update()

    # --- SRS REVIEW LOGIC ---
    def submit_rating(quality: int):
        nonlocal current_card_index, is_front
        if not current_cards:
            return
            
        card_id = current_cards[current_card_index]["id"]
        try:
            requests.post(f"{API_BASE}/cards/{card_id}/review", json={"quality": quality})
        except Exception as err:
            print(f"Failed to record review: {err}")
            
        if current_card_index < len(current_cards) - 1:
            current_card_index += 1
            is_front = True
            update_card_view()
        else:
            card_counter.value = ""
            card_text.value = "🎉 **All caught up!** You have completed all due cards for this deck."
            srs_row.visible = False
            controls_row.visible = True
            page.update()

    # --- CORE FUNCTIONS ---
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
            card_counter.value = ""
            card_text.value = "Please select a deck first."
            page.update()
            return

        try:
            # Fetch due cards first
            response = requests.get(f"{API_BASE}/decks/{deck_id}/due")
            if response.status_code == 200:
                current_cards = response.json().get("due_cards", [])
                
                # If no cards are due, fall back to loading all cards
                if not current_cards:
                    all_resp = requests.get(f"{API_BASE}/decks/{deck_id}/cards")
                    current_cards = all_resp.json().get("cards", [])
                    
                if not current_cards:
                    card_counter.value = ""
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

    def delete_deck_clicked(e):
        nonlocal current_cards, current_card_index, is_front
        deck_id = deck_dropdown.value
        
        if not deck_id:
            card_counter.value = ""
            card_text.value = "Please select a deck to delete first."
            page.update()
            return

        try:
            response = requests.delete(f"{API_BASE}/decks/{deck_id}")
            if response.status_code == 200:
                card_counter.value = ""
                card_text.value = "Deck deleted successfully. The clutter is gone!"
                current_cards = []
                deck_dropdown.value = None
                load_decks()
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
        card_counter.value = f"Card {current_card_index + 1} of {len(current_cards)}"
        card_text.value = card["front"] if is_front else card["back"]
        
        # Display SRS buttons on the back of the card, standard nav on the front
        if not is_front:
            controls_row.visible = False
            srs_row.visible = True
        else:
            controls_row.visible = True
            srs_row.visible = False
            
        page.update()

    # --- BUTTON STYLING ---
    load_btn = ft.FilledButton(
        content="Study Due", 
        on_click=fetch_cards_clicked, 
        style=ft.ButtonStyle(bgcolor=accent_color, color=bg_color)
    )
    
    upload_btn = ft.FilledButton(
        content="Upload PDF", 
        icon=ft.Icons.UPLOAD_FILE, 
        on_click=on_upload_click,
        style=ft.ButtonStyle(bgcolor="#4A4036", color=text_color)
    )

    delete_btn = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        icon_color="#E07A5F", 
        on_click=delete_deck_clicked,
        tooltip="Delete Selected Deck"
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

    # SRS Controls shown when card is flipped
    srs_row = ft.Row(
        [
            ft.FilledButton(content="Hard (1d)", on_click=lambda e: submit_rating(3), style=ft.ButtonStyle(bgcolor="#8F5C38", color=text_color)),
            ft.FilledButton(content="Good (6d)", on_click=lambda e: submit_rating(4), style=ft.ButtonStyle(bgcolor="#4A6B53", color=text_color)),
            ft.FilledButton(content="Easy", on_click=lambda e: submit_rating(5), style=ft.ButtonStyle(bgcolor="#3E6B7E", color=text_color)),
            ft.FilledButton(content="Flip Back", on_click=lambda e: flip_card(), icon=ft.Icons.FLIP, style=nav_btn_style),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15,
        visible=False
    )

    # --- LAYOUT CONSTRUCTION ---
    page.add(
        ft.Row([deck_dropdown, delete_btn, load_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
        ft.Container(height=10),
        ft.Row([slider_container, upload_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
        ft.Container(height=20),
        ft.Row([card_container], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(height=30),
        controls_row,
        srs_row
    )

    load_decks()

ft.run(main)