import flet as ft
import requests
import asyncio

API_BASE = "http://127.0.0.1:8000"

def main(page: ft.Page):
    page.title = "Flap - AI Study App"
    page.bgcolor = "#1F1B18"
    page.padding = 40
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    bg_color = "#1F1B18"
    card_color = "#342D27"
    accent_color = "#D4A373"
    text_color = "#FAEDCD"

    current_cards = []
    current_card_index = 0
    is_front = True

    quiz_mode = False
    quiz_data = []          
    current_quiz_index = 0
    quiz_score = 0          
    quiz_answered = False   
    quiz_explanation_shown = False 
    
    summary_mode = False

    deck_dropdown = ft.Dropdown(label="Select a Deck", width=300, color=text_color)
    card_counter = ft.Text(value="", size=14, color=accent_color, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER)
    card_text = ft.Markdown(value="Select a deck or upload a new PDF!", selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)
    
    progress_ring = ft.ProgressRing(visible=False, color=accent_color)
    quiz_progress_ring = ft.ProgressRing(visible=False, color=accent_color)

    card_content = ft.Column(
        [card_counter, card_text, ft.Container(height=10), progress_ring],
        alignment=ft.MainAxisAlignment.CENTER, 
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
        spacing=10,
        scroll=ft.ScrollMode.AUTO
    )

    card_container = ft.Container(
        content=card_content, width=600, height=550, bgcolor=card_color,
        border_radius=20, padding=40, alignment=ft.Alignment(0, 0),
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=15, color="#000000"),
        on_click=lambda e: flip_card(), animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
    )

    count_label = ft.Text(value="Target Cards: 15", color=text_color, size=16)

    def on_slider_change(e):
        count_label.value = f"Target Cards: {int(e.control.value)}"
        page.update()

    card_slider = ft.Slider(min=5, max=50, divisions=9, value=15, active_color=accent_color, on_change=on_slider_change, width=200)
    slider_container = ft.Column([count_label, card_slider], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)

    quiz_question = ft.Markdown(value="", selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)
    quiz_score_text = ft.Text(value="", color=text_color, size=16, weight=ft.FontWeight.W_600)
    
    quiz_count_label = ft.Text(value="Target Questions: 5", color=text_color, size=16)

    def on_quiz_slider_change(e):
        quiz_count_label.value = f"Target Questions: {int(e.control.value)}"
        page.update()

    quiz_slider = ft.Slider(min=1, max=20, divisions=19, value=5, active_color=accent_color, on_change=on_quiz_slider_change, width=200)
    quiz_slider_container = ft.Column([quiz_count_label, quiz_slider], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0)
    
    quiz_option_buttons = [
        ft.FilledButton(
            content=ft.Text(""), 
            on_click=lambda e, idx=i: check_answer(idx),
            style=ft.ButtonStyle(bgcolor="#4A4036", color=text_color),
            width=500
        ) for i in range(4)
    ]
    # Changed to Column so long answers stack cleanly
    quiz_options_col = ft.Column(quiz_option_buttons, alignment=ft.MainAxisAlignment.CENTER, spacing=10)
    quiz_explanation = ft.Markdown(value="", selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, visible=False)
    
    quiz_next_btn = ft.FilledButton(
        content=ft.Text("Next Question"),
        on_click=lambda e: next_quiz_clicked(e),
        style=ft.ButtonStyle(bgcolor=accent_color, color=bg_color),
        visible=False
    )
    quiz_generate_btn = ft.FilledButton(
        content=ft.Text("Generate Quiz"),
        style=ft.ButtonStyle(bgcolor=accent_color, color=bg_color)
    )
    
    quiz_view_container = ft.Container(
        content=ft.Column(
            [
                ft.Row([quiz_score_text], alignment=ft.MainAxisAlignment.END),
                ft.Container(height=10),
                quiz_question,
                ft.Container(height=20),
                quiz_options_col,
                ft.Container(height=20),
                quiz_explanation,
                ft.Container(height=20),
                quiz_next_btn,
                quiz_slider_container,
                quiz_generate_btn,
                ft.Container(height=20),
                quiz_progress_ring 
            ],
            alignment=ft.MainAxisAlignment.CENTER, 
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
            spacing=0,
            scroll=ft.ScrollMode.AUTO
        ),
        width=600, height=550, bgcolor=card_color, border_radius=20, padding=40,
        alignment=ft.Alignment(0, 0), shadow=ft.BoxShadow(spread_radius=2, blur_radius=15, color="#000000")
    )

    summary_markdown = ft.Markdown(value="", selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)
    summary_progress_ring = ft.ProgressRing(visible=False, color=accent_color)
    summary_loading_text = ft.Text(value="", color=accent_color, size=16, weight=ft.FontWeight.W_600)
    
    def on_back_to_study_click(e):
        toggle_summary_mode(e)
        
    summary_back_btn = ft.FilledButton(
        content=ft.Text("Back to Study"),
        on_click=on_back_to_study_click,
        style=ft.ButtonStyle(bgcolor=accent_color, color=bg_color)
    )

    summary_view_container = ft.Container(
        content=ft.Column(
            [
                summary_loading_text,
                summary_progress_ring,
                summary_markdown,
                ft.Container(height=20),
                summary_back_btn
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            scroll=ft.ScrollMode.AUTO
        ),
        width=600, height=550, bgcolor=card_color, border_radius=20, padding=40,
        alignment=ft.Alignment(0, -1), shadow=ft.BoxShadow(spread_radius=2, blur_radius=15, color="#000000"),
        visible=False
    )

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def on_upload_click(e):
        upload_btn.disabled = True
        upload_btn.content.value = "Uploading..."
        page.update()

        files = await file_picker.pick_files(allowed_extensions=["pdf"])
        if not files:
            upload_btn.disabled = False
            upload_btn.content.value = "Upload PDF"
            page.update()
            return

        selected_file = files[0]
        selected_count = int(card_slider.value)
        card_counter.value = ""
        card_text.value = f"Extracting {selected_count} cards from '{selected_file.name}'...\nThis takes a moment."
        progress_ring.visible = True
        page.update()
        await asyncio.sleep(0.1) # Yields thread to draw the loading ring

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
        upload_btn.disabled = False
        upload_btn.content.value = "Upload PDF"
        page.update()

    def submit_rating(quality: int):
        nonlocal current_card_index, is_front
        if not current_cards: return
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

    async def fetch_cards_clicked(e):
        nonlocal current_cards, current_card_index, is_front
        deck_id = deck_dropdown.value
        if not deck_id:
            card_counter.value = ""
            card_text.value = "Please select a deck first."
            page.update()
            return

        load_btn.disabled = True
        load_btn.content.value = "Loading..."
        progress_ring.visible = True
        card_counter.value = ""
        card_text.value = "Loading cards..."
        page.update()
        await asyncio.sleep(0.1)

        try:
            response = requests.get(f"{API_BASE}/decks/{deck_id}/due")
            if response.status_code == 200:
                current_cards = response.json().get("due_cards", [])
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
        except Exception as err:
            card_text.value = f"App Error: {err}"
        finally:
            progress_ring.visible = False
            load_btn.disabled = False
            load_btn.content.value = "Study Due"
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
        if not current_cards: return
        card = current_cards[current_card_index]
        card_counter.value = f"Card {current_card_index + 1} of {len(current_cards)}"
        card_text.value = card["front"] if is_front else card["back"]

        if not is_front:
            controls_row.visible = False
            srs_row.visible = True
        else:
            controls_row.visible = True
            srs_row.visible = False
        page.update()

    def toggle_quiz_mode(e):
        nonlocal quiz_mode, quiz_data, current_quiz_index, quiz_score, quiz_answered, quiz_explanation_shown, summary_mode
        quiz_mode = not quiz_mode
        if quiz_mode:
            summary_mode = False
            quiz_data = []
            current_quiz_index = 0
            quiz_score = 0
            quiz_answered = False
            quiz_explanation_shown = False
        update_quiz_mode_ui()

    def update_quiz_mode_ui():
        nonlocal quiz_mode
        if quiz_mode:
            card_container.visible = False
            controls_row.visible = False
            srs_row.visible = False
            quiz_view_container.visible = True
            
            if not quiz_data:
                quiz_generate_btn.visible = True
                quiz_slider_container.visible = True
                quiz_question.value = "Select a deck and click 'Generate Quiz' to start"
                quiz_options_col.visible = False
                quiz_explanation.visible = False
                quiz_next_btn.visible = False
                quiz_score_text.value = ""
            else:
                quiz_generate_btn.visible = False
                quiz_slider_container.visible = False
                quiz_options_col.visible = True 
                update_quiz_view() 
        else:
            card_container.visible = True
            controls_row.visible = True
            srs_row.visible = not is_front 
            quiz_view_container.visible = False
        page.update()

    def toggle_summary_mode(e):
        nonlocal summary_mode, quiz_mode
        summary_mode = not summary_mode
        if summary_mode:
            quiz_mode = False
            card_container.visible = False
            controls_row.visible = False
            srs_row.visible = False
            quiz_view_container.visible = False
            summary_view_container.visible = True
            
            summary_markdown.value = ""
            summary_loading_text.value = ""
            
            page.run_task(fetch_or_generate_summary)
        else:
            summary_view_container.visible = False
            card_container.visible = True
            controls_row.visible = True
            srs_row.visible = not is_front
            
        page.update()

    async def fetch_or_generate_summary(e=None):
        deck_id = deck_dropdown.value
        if not deck_id:
            summary_markdown.value = "Please select a deck first."
            page.update()
            return
            
        summary_progress_ring.visible = True
        summary_loading_text.value = "Fetching cheat sheet..."
        summary_back_btn.disabled = True
        page.update()
        
        try:
            response = requests.get(f"{API_BASE}/decks/{deck_id}/summary")
            if response.status_code == 200:
                summary_markdown.value = response.json().get("markdown_content", "")
                summary_loading_text.value = ""
            elif response.status_code == 404:
                summary_loading_text.value = "Drafting executive summary...\nThis may take a minute."
                page.update()
                
                await asyncio.sleep(0.1)
                
                gen_resp = requests.post(f"{API_BASE}/decks/{deck_id}/generate-summary")
                if gen_resp.status_code == 200:
                    summary_markdown.value = gen_resp.json().get("markdown_content", "")
                    summary_loading_text.value = ""
                else:
                    summary_markdown.value = f"Error generating: {gen_resp.status_code} - {gen_resp.text}"
                    summary_loading_text.value = ""
            else:
                summary_markdown.value = f"Backend Error: {response.status_code}"
                summary_loading_text.value = ""
        except Exception as err:
            summary_markdown.value = f"App Error: {err}"
            summary_loading_text.value = ""
            
        summary_progress_ring.visible = False
        summary_back_btn.disabled = False
        page.update()

    async def generate_quiz_clicked(e):
        nonlocal quiz_data, current_quiz_index, quiz_score, quiz_answered, quiz_explanation_shown
        deck_id = deck_dropdown.value
        if not deck_id:
            quiz_question.value = "Please select a deck first."
            quiz_options_col.visible = False
            quiz_explanation.visible = False
            quiz_next_btn.visible = False
            page.update()
            return

        quiz_generate_btn.disabled = True
        quiz_generate_btn.content.value = "Generating..."
        quiz_slider_container.visible = False
        quiz_progress_ring.visible = True
        quiz_question.value = "Generating quiz..."
        quiz_options_col.visible = False
        quiz_explanation.visible = False
        quiz_next_btn.visible = False
        page.update()
        await asyncio.sleep(0.1) 

        try:
            quiz_count = int(quiz_slider.value)
            response = requests.post(f"{API_BASE}/decks/{deck_id}/generate-quiz?count={quiz_count}")
            if response.status_code != 200:
                quiz_question.value = f"Error generating quiz: {response.status_code}"
                return

            quiz_response = requests.get(f"{API_BASE}/decks/{deck_id}/quizzes")
            if quiz_response.status_code != 200:
                quiz_question.value = f"Error fetching quiz: {quiz_response.status_code}"
                return

            quiz_data = quiz_response.json().get("quizzes", [])
            if not quiz_data:
                quiz_question.value = "No quiz data generated. Try again."
                return

            current_quiz_index = 0
            quiz_score = 0
            quiz_answered = False
            quiz_explanation_shown = False
            quiz_generate_btn.visible = False
            update_quiz_view()
        except Exception as err:
            quiz_question.value = f"Quiz generation failed: {err}"
        finally:
            quiz_generate_btn.disabled = False
            quiz_generate_btn.content.value = "Generate Quiz"
            quiz_progress_ring.visible = False
            page.update()

    def update_quiz_view():
        nonlocal quiz_data, current_quiz_index, quiz_score, quiz_answered, quiz_explanation_shown
        if not quiz_data or current_quiz_index >= len(quiz_data):
            quiz_question.value = "Quiz Complete!"
            quiz_options_col.visible = False
            quiz_explanation.value = f"You scored {quiz_score} out of {len(quiz_data)}."
            quiz_explanation.visible = True
            quiz_next_btn.visible = False
            quiz_score_text.value = f"Final Score: {quiz_score}/{len(quiz_data)}"
            page.update()
            return

        quiz = quiz_data[current_quiz_index]
        quiz_question.value = quiz["question"]
        quiz_score_text.value = f"Score: {quiz_score}/{len(quiz_data)}"

        options = quiz["options"]
        explanation = quiz["explanation"]

        for i, btn in enumerate(quiz_option_buttons):
            if i < len(options):
                btn.content.value = options[i]
                btn.disabled = False
                btn.style = ft.ButtonStyle(bgcolor="#4A4036", color=text_color)
                btn.visible = True
            else:
                btn.visible = False 

        quiz_options_col.visible = True
        quiz_explanation.value = explanation
        quiz_explanation.visible = False
        quiz_next_btn.visible = False
        quiz_answered = False
        quiz_explanation_shown = False
        page.update()

    def check_answer(option_index):
        nonlocal quiz_answered, quiz_score, quiz_explanation_shown
        if quiz_answered: return
        quiz_answered = True
        quiz = quiz_data[current_quiz_index]
        correct_answer = quiz["correct_answer"] 

        is_correct = (option_index == correct_answer)

        if is_correct:
            quiz_score += 1
            quiz_option_buttons[option_index].style = ft.ButtonStyle(bgcolor="#3E6B7E", color=text_color) 
        else:
            quiz_option_buttons[option_index].style = ft.ButtonStyle(bgcolor="#8F5C38", color=text_color) 
            if correct_answer < len(quiz_option_buttons):
                quiz_option_buttons[correct_answer].style = ft.ButtonStyle(bgcolor="#3E6B7E", color=text_color)

        quiz_score_text.value = f"Score: {quiz_score}/{len(quiz_data)}"
        quiz_explanation.visible = True
        quiz_next_btn.visible = True
        page.update()

    def next_quiz_clicked(e):
        nonlocal current_quiz_index
        current_quiz_index += 1
        update_quiz_view()

    load_btn = ft.FilledButton(content=ft.Text("Study Due"), on_click=fetch_cards_clicked, style=ft.ButtonStyle(bgcolor=accent_color, color=bg_color))
    upload_btn = ft.FilledButton(content=ft.Text("Upload PDF"), icon=ft.Icons.UPLOAD_FILE, on_click=on_upload_click, style=ft.ButtonStyle(bgcolor="#4A4036", color=text_color))
    delete_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color="#E07A5F", on_click=delete_deck_clicked, tooltip="Delete Selected Deck")
    quiz_toggle_btn = ft.IconButton(icon=ft.Icons.QUIZ, icon_color=accent_color, on_click=toggle_quiz_mode, tooltip="Switch to Quiz Mode")

    nav_btn_style = ft.ButtonStyle(bgcolor="#4A4036", color=text_color, shape=ft.RoundedRectangleBorder(radius=10))

    controls_row = ft.Row(
        [
            ft.FilledButton(content=ft.Text("Previous"), on_click=prev_card, icon=ft.Icons.ARROW_BACK, style=nav_btn_style),
            ft.FilledButton(content=ft.Text("Flip Card"), on_click=lambda e: flip_card(), icon=ft.Icons.FLIP, style=nav_btn_style),
            ft.FilledButton(content=ft.Text("Next"), on_click=next_card, icon=ft.Icons.ARROW_FORWARD, style=nav_btn_style),
        ],
        alignment=ft.MainAxisAlignment.CENTER, spacing=15
    )

    srs_row = ft.Row(
        [
            ft.FilledButton(content=ft.Text("Hard (1d)"), on_click=lambda e: submit_rating(3), style=ft.ButtonStyle(bgcolor="#8F5C38", color=text_color)),
            ft.FilledButton(content=ft.Text("Good (6d)"), on_click=lambda e: submit_rating(4), style=ft.ButtonStyle(bgcolor="#4A6B53", color=text_color)),
            ft.FilledButton(content=ft.Text("Easy"), on_click=lambda e: submit_rating(5), style=ft.ButtonStyle(bgcolor="#3E6B7E", color=text_color)),
            ft.FilledButton(content=ft.Text("Flip Back"), on_click=lambda e: flip_card(), icon=ft.Icons.FLIP, style=nav_btn_style),
        ],
        alignment=ft.MainAxisAlignment.CENTER, spacing=15, visible=False
    )

    cheat_sheet_btn = ft.FilledButton(content=ft.Text("Cheat Sheet"), icon=ft.Icons.ARTICLE, on_click=toggle_summary_mode, style=ft.ButtonStyle(bgcolor="#4A4036", color=text_color))
    row1_controls = ft.Row([deck_dropdown, delete_btn, load_btn, quiz_toggle_btn, cheat_sheet_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=15)

    quiz_generate_btn.on_click = generate_quiz_clicked

    focus_trap = ft.TextField(width=1, height=1, border=ft.InputBorder.NONE, color=ft.Colors.TRANSPARENT, bgcolor=ft.Colors.TRANSPARENT, cursor_color=ft.Colors.TRANSPARENT)

    async def on_keyboard(e: ft.KeyboardEvent):
        handled = False
        if e.key == " " or e.key == "Space":
            if not quiz_mode and not summary_mode and current_cards:
                flip_card()
                handled = True
        elif e.key == "Arrow Right" or e.key == "Enter":
            if not quiz_mode and not summary_mode:
                next_card(None)
                handled = True
            elif quiz_mode and not summary_mode and quiz_next_btn.visible:
                next_quiz_clicked(None)
                handled = True
        elif e.key == "Arrow Left":
            if not quiz_mode and not summary_mode:
                prev_card(None)
                handled = True
        elif e.key in ["1", "2", "3", "4"]:
            if quiz_mode and not quiz_answered and quiz_options_col.visible:
                option_index = int(e.key) - 1
                check_answer(option_index)
                handled = True
                
        if handled:
            try:
                await focus_trap.focus()
            except Exception:
                pass

    page.on_keyboard_event = on_keyboard

    page.add(
        focus_trap,
        row1_controls,
        ft.Container(height=10),
        ft.Row([slider_container, upload_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
        ft.Container(height=20),
        ft.Stack([card_container, quiz_view_container, summary_view_container]),
        ft.Container(height=30),
        controls_row,
        srs_row
    )

    load_decks()
    update_quiz_mode_ui() 

ft.run(main)