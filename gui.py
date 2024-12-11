import tkinter as tk


count = 5
def create_window():
    root = tk.Tk()
    root.overrideredirect(True) # remove title bar
    root.configure(bg="black")
    root.attributes('-alpha', 0.8) # transparency 
    root.wm_attributes('-topmost', True)
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 500
    window_height = 60
    x = (screen_width - window_width) //2
    y = int((screen_height - window_height) *.8)
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    label = tk.Label(root, text="5", font=("Arial", 40),fg="white",bg="black")
    label.pack()

    def start_move(event):
        root.x = event.x
        root.y = event.y

    def on_motion(event):
        delta_x = event.x - root.x
        delta_y = event.y - root.y
        root.geometry(f"+{root.winfo_x() + delta_x}+{root.winfo_y() + delta_y}")

    root.bind('<Button-1>', start_move)
    root.bind('<B1-Motion>', on_motion)

    # 倒计时函数
    def countdown():
        global count
        count -= 1
        label.config(text=count)
        if count > 0:
            root.after(1000, countdown)
        else:
            root.destroy()


    countdown()

    root.mainloop()

create_window()