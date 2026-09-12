import flet as ft

def main(page: ft.Page):
    btn1 = ft.FilledButton("Btn1")
    btn2 = ft.FilledButton("Btn2")
    trap = ft.TextField(width=0, height=0, border=ft.InputBorder.NONE)
    
    def on_key(e: ft.KeyboardEvent):
        print("Key pressed:", e.key)
        trap.focus()
        page.update()
        
    page.on_keyboard_event = on_key
    page.add(ft.Row([btn1, btn2]), trap)
    trap.focus()

ft.app(target=main)
