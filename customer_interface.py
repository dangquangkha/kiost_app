import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
import qrcode
import time
from PIL import Image, ImageTk
import io
import os
import speech_recognition as sr
from openai import OpenAI
import threading
import pygame
import re
from dotenv import load_dotenv

# --- CẤU HÌNH CỦA BẠN ---
HEROKU_APP_URL = "https://khai-flask-todo-app-a81bf71c8cf2.herokuapp.com/"
# -------------------------

# --- CẤU HÌNH VOICE (Giữ nguyên) ---
try:
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY không được tìm thấy.")
    client = OpenAI(api_key=openai_api_key)
except Exception as e:
    # MODIFIED: Không hiển thị popup ở đây vì root chưa được tạo
    print(f"Lỗi OpenAI Key: Không tìm thấy OPENAI_API_KEY. {e}")
    # exit() # Cân nhắc thoát nếu không có key

recognizer = sr.Recognizer()
pygame.mixer.init()
# -------------------------

# --- BIẾN TOÀN CỤC ---
current_orderId = None
root = None
menu_items = {}
shopping_cart = {}
status_label = None
menu_frame = None
checkout_frame = None
payment_frame = None
cart_summary_label = None
checkout_details_label = None
qr_label = None
keypad_frame = None
keypad_display_var = None
keypad_item_label = None
current_item_for_keypad = None
voice_button = None
conversation_history = []
chat_system_prompt = ""
idle_frame = None
is_busy = False  # Biến kiểm tra xem robot đang rảnh hay đang phục vụ
# --- BIẾN MỚI CHO LOGIC ROBOT ---
CURRENT_TABLE = None # Sẽ lưu số bàn robot đang phục vụ
CURRENT_SERVICE_REQUEST_ID = None # Sẽ lưu ID của yêu cầu phục vụ
# ---------------------------------

# --- HÀM TẢI MENU (Giữ nguyên) ---
def load_menu_from_server():
    # ... (Giữ nguyên toàn bộ nội dung hàm) ...
    global menu_items
    try:
        url = f"{HEROKU_APP_URL}/api/get-menu"
        print(f"Đang tải menu từ {url}...")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            menu_items = response.json()
            print(f"Tải menu thành công: {menu_items}")
            
            if not menu_items:
                 # MODIFIED: Không hiển thị popup
                 print("Lỗi Menu: Không tìm thấy món nào trong menu từ server.")
                 return False
            return True
        else:
            raise Exception(f"Server báo lỗi: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Lỗi Mạng: Không thể tải thực đơn từ server: {e}")
        return False

# --- CÁC HÀM HELPER (Giữ nguyên) ---
# add_to_cart, update_cart_summary, calculate_total_amount,
# get_order_info_string, get_cart_details_text,
# show_keypad_screen, keypad_press, keypad_clear, keypad_cancel, keypad_enter,
# show_menu_screen, show_checkout_screen, show_payment_qr_screen
# ... (Giữ nguyên toàn bộ nội dung các hàm này) ...
def add_to_cart(item_name):
    """
    MODIFIED: Chỉ gọi màn hình bàn phím số, không dùng simpledialog.
    """
    show_keypad_screen(item_name)
def update_cart_summary():
    """Cập nhật Label tóm tắt giỏ hàng."""
    global cart_summary_label
    
    if not shopping_cart:
        cart_summary_label.config(text="Giỏ hàng trống")
        return

    total_items = sum(shopping_cart.values())
    total_amount = calculate_total_amount()
    
    summary_text = f"Giỏ hàng: {total_items} món - {total_amount:,} VND"
    cart_summary_label.config(text=summary_text)

def calculate_total_amount():
    """Tính tổng tiền từ giỏ hàng."""
    total = 0
    for item, quantity in shopping_cart.items():
        total += menu_items[item]['price'] * quantity
    return total

def get_order_info_string():
    """Tạo chuỗi thông tin đơn hàng (ví dụ: '2x Coca, 1x Pepsi')."""
    if not shopping_cart:
        return "Đơn hàng trống"
    
    parts = [f"{qty}x {item}" for item, qty in shopping_cart.items()]
    return ", ".join(parts)

def get_cart_details_text():
    """Tạo chuỗi chi tiết giỏ hàng cho màn hình thanh toán."""
    if not shopping_cart:
        return "Giỏ hàng trống"

    lines = ["Chi tiết đơn hàng:"]
    total = 0
    for item, quantity in shopping_cart.items():
        price = menu_items[item]['price']
        subtotal = price * quantity
        lines.append(f" - {item}: {quantity} x {price:,} = {subtotal:,} VND")
        total += subtotal
    
    lines.append("--------------------")
    lines.append(f"TỔNG CỘNG: {total:,} VND")
    return "\n".join(lines)

# --- HÀM XỬ LÝ ẢNH ĐA NĂNG (ONLINE + LOCAL) ---
image_cache = {} 

# Trong customer_interface.py, thay thế hàm load_product_image bằng đoạn này:

def load_product_image(image_path):
    """
    Hàm thông minh: Tải ảnh Online (có giả lập trình duyệt) hoặc Offline.
    """
    if not image_path:
        return get_default_image()

    # Kiểm tra Cache
    if image_path in image_cache:
        return image_cache[image_path]

    try:
        pil_image = None
        
        # TRƯỜNG HỢP 1: Link Online (http/https)
        if image_path.startswith("http"):
            print(f"Đang tải ảnh online: {image_path}")
            
            # --- SỬA ĐỔI QUAN TRỌNG: THÊM HEADERS ĐỂ GIẢ LẬP TRÌNH DUYỆT ---
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            # Thêm headers vào request
            response = requests.get(image_path, headers=headers, timeout=5) 
            response.raise_for_status() # Báo lỗi nếu server trả về 403/404
            
            img_data = response.content
            pil_image = Image.open(io.BytesIO(img_data))
            
        # TRƯỜNG HỢP 2: File trên máy tính (Local)
        else:
            if os.path.exists(image_path):
                pil_image = Image.open(image_path)
            else:
                print(f"Không tìm thấy file ảnh: {image_path}")
                return get_default_image()

        # Resize chung
        pil_image = pil_image.resize((120, 120), Image.LANCZOS)
        tk_image = ImageTk.PhotoImage(pil_image)
        
        # Lưu vào cache
        image_cache[image_path] = tk_image
        return tk_image

    except Exception as e:
        print(f"Lỗi xử lý ảnh (Có thể do link bị chặn): {e}")
        return get_default_image()

def get_default_image():
    """Tạo một ô màu xám nếu không có ảnh"""
    if "default" in image_cache: return image_cache["default"]
    
    pil_image = Image.new('RGB', (120, 120), color='#CCCCCC')
    tk_image = ImageTk.PhotoImage(pil_image)
    image_cache["default"] = tk_image
    return tk_image


def create_product_card(parent_frame, item_name, price,image_url, row, col):
    """Tạo một thẻ sản phẩm đẹp mắt thay vì nút bấm thường."""
    
    # 1. Frame bao ngoài (Card)
    card = tk.Frame(parent_frame, bg="white", bd=2, relief="flat")
    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
    
    # Hiệu ứng shadow giả (optional): dùng border
    card.config(highlightbackground="#E0E0E0", highlightthickness=1)

    # 2. Hình ảnh
    img = load_product_image(image_url)
    img_label = tk.Label(card, image=img, bg="white", cursor="hand2")
    img_label.pack(pady=(10, 5))

    # 3. Tên món
    name_label = tk.Label(card, text=item_name, font=("Helvetica", 11, "bold"), 
                          bg="white", fg="#333333", wraplength=140, cursor="hand2")
    name_label.pack(padx=5)

    # 4. Giá tiền
    price_label = tk.Label(card, text=f"{price:,} đ", font=("Arial", 12, "bold"), 
                           bg="white", fg="#FF5722", cursor="hand2") # Màu cam nổi bật
    price_label.pack(pady=(0, 10))

    # 5. Sự kiện Click (Gán cho cả Frame, Ảnh, và Text để bấm đâu cũng ăn)
    def on_click(e):
        add_to_cart(item_name)
        # Hiệu ứng nháy nhẹ khi bấm
        card.config(bg="#E3F2FD") # Xanh nhạt
        root.after(100, lambda: card.config(bg="white"))

    card.bind("<Button-1>", on_click)
    img_label.bind("<Button-1>", on_click)
    name_label.bind("<Button-1>", on_click)
    price_label.bind("<Button-1>", on_click)

    return card

def show_keypad_screen(item_name):
    """Hiển thị màn hình bàn phím số."""
    global current_item_for_keypad
    current_item_for_keypad = item_name
    
    # Cập nhật tiêu đề cho món ăn
    keypad_item_label.config(text=f"Nhập số lượng cho: {item_name}")
    keypad_clear() # Xóa số lượng cũ
    
    status_label.config(text="Mời bạn nhập số lượng")

    # Ẩn các frame khác
    menu_frame.pack_forget()
    if checkout_frame:
        checkout_frame.pack_forget()
    if payment_frame:
        payment_frame.pack_forget()
    
    # Hiển thị frame bàn phím
    keypad_frame.pack(fill="both", expand=True)

def keypad_press(number):
    """Xử lý khi nhấn một nút số."""
    current_val = keypad_display_var.get()
    # Giới hạn 2 chữ số (max 99)
    if len(current_val) < 2:
        keypad_display_var.set(current_val + str(number))

def keypad_clear():
    """Xóa màn hình số."""
    keypad_display_var.set("")

def keypad_cancel():
    """Hủy nhập số lượng và quay lại menu."""
    keypad_clear()
    show_menu_screen()

def keypad_enter():
    """Xác nhận số lượng và thêm vào giỏ hàng."""
    global shopping_cart, current_item_for_keypad
    
    quantity_str = keypad_display_var.get()
    
    # Kiểm tra đầu vào
    if not quantity_str:
        messagebox.showwarning("Lỗi", "Vui lòng nhập số lượng.")
        return
        
    try:
        quantity = int(quantity_str)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Lỗi", "Số lượng không hợp lệ.")
        keypad_clear()
        return

    # Lấy tên món đã lưu
    item_name = current_item_for_keypad
    
    # Thêm vào giỏ hàng (logic từ hàm add_to_cart cũ)
    shopping_cart[item_name] = shopping_cart.get(item_name, 0) + quantity
    print(f"Giỏ hàng (từ keypad): {shopping_cart}")
    
    # Cập nhật và quay về
    update_cart_summary()
    show_menu_screen()
def show_menu_screen():
    """Hiển thị màn hình chọn món."""
    status_label.config(text="Mời bạn chọn đồ uống")
    
    if checkout_frame:
        checkout_frame.pack_forget()
    if payment_frame:
        payment_frame.pack_forget()
    if keypad_frame:
        keypad_frame.pack_forget()
        
    menu_frame.pack(fill="both", expand=True)
    update_cart_summary()

def show_idle_screen():
    """Hiển thị màn hình chờ thân thiện."""
    global status_label, is_busy
    
    is_busy = False # Đánh dấu là robot đang rảnh
    
    # Ẩn tất cả các frame phục vụ
    if menu_frame: menu_frame.pack_forget()
    if checkout_frame: checkout_frame.pack_forget()
    if payment_frame: payment_frame.pack_forget()
    if keypad_frame: keypad_frame.pack_forget()
    
    # Cập nhật trạng thái
    if status_label:
        status_label.config(text="🤖 Robot đang chờ lệnh phục vụ...", fg="green")
    
    # Hiển thị frame chờ
    if idle_frame:
        idle_frame.pack(fill="both", expand=True)

# --- HÀM POLLING MỚI (THAY THẾ robot_idle_loop CŨ) ---
def check_for_new_orders():
    """
    Hàm này sẽ chạy liên tục mỗi 5 giây nhờ root.after
    để kiểm tra xem có đơn hàng mới không.
    """
    global is_busy, CURRENT_TABLE, CURRENT_SERVICE_REQUEST_ID
    
    # Nếu đang phục vụ khách, thì KHÔNG kiểm tra đơn mới (để tránh xung đột)
    if is_busy:
        root.after(5000, check_for_new_orders) # Gọi lại sau 5s
        return

    print(f"[{time.strftime('%H:%M:%S')}] Đang kiểm tra lệnh gọi phục vụ...", end='\r')
    
    try:
        url = f"{HEROKU_APP_URL}/api/get-service-requests"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            requests_list = response.json()
            
            if requests_list:
                # --- TÌM THẤY LỆNH MỚI ---
                service_req = requests_list[0]
                CURRENT_TABLE = service_req.get('table_number')
                CURRENT_SERVICE_REQUEST_ID = service_req.get('request_id')
                
                print(f"\n🔔 CÓ LỆNH MỚI! Bàn {CURRENT_TABLE}")
                
                # Báo server đã nhận
                try:
                    requests.post(f"{HEROKU_APP_URL}/api/complete-service-request/{CURRENT_SERVICE_REQUEST_ID}", timeout=5)
                except:
                    pass
                
                # CHUYỂN SANG CHẾ ĐỘ PHỤC VỤ
                start_serving_customer() 
                return # Thoát hàm để dừng poll tạm thời, chờ lệnh phục vụ xong
                
    except Exception as e:
        print(f"\nLỗi kết nối: {e}")

    # Lên lịch chạy lại hàm này sau 5000ms (5 giây)
    if root:
        root.after(5000, check_for_new_orders)

# --- HÀM BẮT ĐẦU PHỤC VỤ (MỚI) ---
def start_serving_customer():
    global is_busy, shopping_cart, current_orderId, conversation_history
    
    is_busy = True # Đánh dấu đang bận
    idle_frame.pack_forget() # Ẩn màn hình chờ
    
    # Reset dữ liệu
    shopping_cart = {}
    current_orderId = None
    
    # Setup lại ngữ cảnh AI
    menu_string = ", ".join([f"{name}" for name in menu_items.keys()])
    chat_system_prompt = (f"Bạn là robot phục vụ Bàn {CURRENT_TABLE}. Menu: {menu_string}.")
    conversation_history = [{"role": "system", "content": chat_system_prompt}]
    
    # Chào khách
    speak(f"Xin chào bàn số {CURRENT_TABLE}, tôi đã đến rồi đây.")
    
    # Hiện menu
    show_menu_screen()
    
    # Tiếp tục vòng lặp kiểm tra đơn (nhưng nó sẽ bị chặn bởi if is_busy)
    root.after(5000, check_for_new_orders)


def show_checkout_screen():
    """Hiển thị màn hình chọn phương thức thanh toán."""
    if not shopping_cart:
        messagebox.showwarning("Lỗi", "Giỏ hàng của bạn đang trống!")
        return
        
    status_label.config(text="Xác nhận đơn hàng và thanh toán")

    menu_frame.pack_forget()
    payment_frame.pack_forget()
    if keypad_frame:
        keypad_frame.pack_forget()
        
    checkout_details_label.config(text=get_cart_details_text())
    
    checkout_frame.pack(fill="both", expand=True)

def show_payment_qr_screen():
    """Hiển thị màn hình quét mã QR."""
    status_label.config(text="Quét mã để thanh toán")
    
    menu_frame.pack_forget()
    checkout_frame.pack_forget()
    if keypad_frame:
        keypad_frame.pack_forget()
        
    payment_frame.pack(fill="both", expand=True)


# --- HÀM MỚI: KẾT THÚC VÀ QUAY VỀ CHỜ ---
# --- SỬA LẠI HÀM finish_and_go_home ---
def finish_and_go_home():
    """Thay vì đóng cửa sổ, ta chỉ quay về màn hình chờ."""
    print("Kết thúc phiên, quay về màn hình chờ.")
    show_idle_screen()
    # KHÔNG GỌI threading.Thread Ở ĐÂY NỮA!

# --- HÀM XỬ LÝ THANH TOÁN (MODIFIED) ---

def handle_qr_payment():
    """MODIFIED: Xử lý khi nhấn nút 'Thanh toán QR'."""
    global CURRENT_TABLE
    print("Bắt đầu thanh toán QR...")
    show_payment_qr_screen()
    
    total_amount = str(calculate_total_amount())
    order_info = get_order_info_string()
    
    # MODIFIED: Gửi kèm số bàn
    start_payment(total_amount, order_info, CURRENT_TABLE)

def handle_cash_payment():
    """MODIFIED: Xử lý khi nhấn nút 'Thanh toán tại quầy'."""
    global CURRENT_TABLE
    print("Bắt đầu gửi đơn hàng tiền mặt...")

    order_info = get_order_info_string()
    total_amount = calculate_total_amount()

    status_label.config(text="Đang gửi đơn hàng, vui lòng chờ...", fg="blue")
    root.update_idletasks()

    try:
        url = f"{HEROKU_APP_URL}/api/create-cash-order"
        payload = {
            'info': order_info,
            'amount': total_amount,
            'table': CURRENT_TABLE # <-- MODIFIED: Gửi kèm số bàn
        }
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 201:
            messagebox.showinfo(
                "Đã gửi đơn hàng",
                f"Đã gửi đơn hàng tới quầy.\nVui lòng đến quầy để thanh toán số tiền: {total_amount:,} VND"
            )
            # MODIFIED: Quay về chế độ chờ
            finish_and_go_home()
        else:
            raise Exception(f"Server báo lỗi: {response.json().get('error', 'Lỗi không xác định')}")

    except Exception as e:
        print(f"Lỗi khi tạo đơn tiền mặt: {e}")
        messagebox.showerror("Lỗi", f"Không thể gửi đơn hàng: {e}")
        show_checkout_screen()

def start_payment(amount, info, table): # <-- MODIFIED: Thêm 'table'
    """
    MODIFIED: Bắt đầu quá trình thanh toán (gửi kèm số bàn).
    """
    global current_orderId, root, qr_label
    
    status_label.config(text="Đang xử lý, vui lòng chờ...", fg="blue")
    root.update_idletasks() 
    
    try:
        print(f"Yêu cầu tạo thanh toán cho {info} - {amount}VND - Bàn {table}")
        # MODIFIED: Thêm &table={table} vào URL
        url = f"{HEROKU_APP_URL}/create-payment?amount={amount}&info={info}&table={table}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"Server Heroku báo lỗi: {response.text}")
        
        # ... (Phần còn lại của hàm tạo QR giữ nguyên) ...
        data = response.json()
        pay_url = data.get('payUrl')
        current_orderId = data.get('orderId')
        if not pay_url or not current_orderId:
            raise Exception("Phản hồi từ server không hợp lệ.")
        qr_img = qrcode.make(pay_url)
        img_byte_arr = io.BytesIO()
        qr_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        img = Image.open(img_byte_arr)
        img = img.resize((250, 250))
        qr_photo = ImageTk.PhotoImage(img)
        qr_label.config(image=qr_photo)
        qr_label.image = qr_photo
        status_label.config(text=f"Quét mã để thanh toán cho {info}...")
        print(f"Bắt đầu Polling cho Order ID: {current_orderId}")
        root.after(3000, poll_for_payment)

    except Exception as e:
        print(f"Lỗi trong start_payment: {e}")
        messagebox.showerror("Lỗi Mạng", f"Không thể tạo thanh toán: {e}")
        reset_kiosk() # Nếu lỗi thì reset về menu

def poll_for_payment():
    """
    MODIFIED: Khi thanh toán thành công, quay về chế độ chờ.
    """
    global current_orderId, root
    if not current_orderId: return
    try:
        url = f"{HEROKU_APP_URL}/check-status?orderId={current_orderId}"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            raise Exception("Server Heroku không phản hồi.")
        status = response.json().get('status')
        print(f"Trạng thái nhận được: {status}")

        if status == 'paid':
            print("THANH TOÁN THÀNH CÔNG!")
            status_label.config(text="Thanh toán thành công! Mời bạn đợi...", fg="green")
            qr_label.config(image=None)
            qr_label.image = None
            
            # MODIFIED: Quay về chế độ chờ sau 5 giây
            root.after(5000, finish_and_go_home) 
            
        elif status == 'pending':
            root.after(3000, poll_for_payment)
        else:
            raise Exception("Thanh toán thất bại hoặc không tìm thấy.")
    except Exception as e:
        print(f"Lỗi polling: {e}")
        messagebox.showerror("Lỗi", f"Lỗi khi kiểm tra thanh toán: {e}")
        reset_kiosk() # Nếu lỗi thì reset về menu

# --- HÀM QUẢN LÝ GIAO DIỆN ---
def reset_kiosk():
    """
    MODIFIED: Reset giao diện VÀ giỏ hàng.
    Hàm này giờ chỉ quay về menu (trong trường hợp khách HỦY).
    """
    global current_orderId, shopping_cart
    print("Resetting Kiosk (quay về menu)...")
    current_orderId = None
    shopping_cart = {}
    if qr_label:
        qr_label.config(image=None)
        qr_label.image = None
    show_menu_screen()

# --- CÁC HÀM VOICE (Giữ nguyên) ---
# speak, listen, get_openai_response,
# process_voice_command, start_voice_thread, voice_loop
# ... (Giữ nguyên toàn bộ nội dung các hàm này) ...
def speak(text):
    """Chuyển văn bản thành giọng nói (OpenAI TTS) và phát bằng pygame.Sound."""
    global status_label
    print(f"🤖 Robot: {text}")
    # Đảm bảo root đã tồn tại trước khi gọi .after
    if root:
        root.after(0, status_label.config, {"text": f"Robot: {text}", "fg": "blue"})
    try:
        filename = "voice_order_response.mp3"
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="alloy",
            input=text
        ) as response:
            response.stream_to_file(filename)
        sound = pygame.mixer.Sound(filename)
        sound.play()
        pygame.time.wait(int(sound.get_length() * 1000))
        os.remove(filename)
    except Exception as e:
        print(f"❌ Lỗi khi chuyển văn bản thành giọng nói: {e}")
        if root:
            root.after(0, status_label.config, {"text": f"Lỗi phát âm thanh: {e}", "fg": "red"})

def listen():
    """Nghe từ micro và trả về văn bản."""
    global status_label, recognizer
    with sr.Microphone() as source:
        if root: root.after(0, status_label.config, {"text": "🎧 Đang nghe...", "fg": "black"})
        print("🎧 Đang nghe...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            if root: root.after(0, status_label.config, {"text": "Đang xử lý...", "fg": "gray"})
            text = recognizer.recognize_google(audio, language="vi-VN")
            print(f"👤 Bạn: {text}")
            if root: root.after(0, status_label.config, {"text": f"Bạn: {text}", "fg": "black"})
            return text.lower()
        except sr.WaitTimeoutError:
            if root: root.after(0, status_label.config, {"text": "Không phát hiện được giọng nói.", "fg": "gray"})
            return None
        except sr.UnknownValueError:
            speak("Xin lỗi, tôi không nghe rõ.")
            return None
        except sr.RequestError:
            speak("Lỗi kết nối dịch vụ nhận dạng giọng nói.")
            return None
def get_openai_response(user_input):
    """
    Hàm MỚI: Gửi câu hỏi đến OpenAI và lấy câu trả lời.
    """
    global conversation_history
    conversation_history.append({"role": "user", "content": user_input})
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history,
            temperature=0.7,
            max_tokens=500,
        )
        ai_response = response.choices[0].message.content.strip()
        conversation_history.append({"role": "assistant", "content": ai_response})
        return ai_response
    except Exception as e:
        print(f"Lỗi khi gọi API: {e}")
        conversation_history.pop()
        return "Tôi đang gặp một chút sự cố, bạn vui lòng thử lại sau nhé."
def process_voice_command(text):
    """
    Phân tích câu nói của người dùng:
    1. Ưu tiên các hành động (đặt món, thanh toán, xóa).
    2. Nếu không phải, chuyển sang cho AI (OpenAI) trả lời.
    """
    global shopping_cart, menu_items
    text_lower = text.lower()
    # --- 1. LOGIC PHÁT NHẠC (MỚI THÊM) ---
    # Kiểm tra xem câu nói có chứa cụm từ khóa không
    if "biết ông thương không" in text_lower:
        speak("Dạ biết chứ, để em mở cho anh nghe nè.")
        # Đợi robot nói xong câu trên rồi mới mở nhạc (khoảng 2 giây)
        if root:
            root.after(2000, lambda: play_music_file(r"D:\AI_VoiceChat\Re_Robot\Kiosk_Robot\know_thuong.mp3")) # <-- Tên file nhạc của bạn
        return

    if "dừng nhạc" in text_lower or "tắt nhạc" in text_lower:
        pygame.mixer.music.stop()
        speak("Đã tắt nhạc.")
        return
    
    num_map = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5}
    
    if "thanh toán" in text_lower:
        speak("Vâng, chuyển đến màn hình thanh toán.")
        root.after(10, show_checkout_screen)
        return
    if "xóa giỏ hàng" in text_lower or "làm lại" in text_lower or "hủy đơn" in text_lower:
        speak("Đã xóa giỏ hàng. Mời bạn chọn lại.")
        root.after(10, reset_kiosk)
        return

    found_items = {}
    words = text_lower.split()
    current_qty = 1
    for i, word in enumerate(words):
        if word in num_map:
            current_qty = num_map[word]
        elif word.isdigit():
            current_qty = int(word)
        possible_item_1 = word
        possible_item_2 = " ".join(words[i:i+2])
        for item_name in menu_items.keys():
            item_lower = item_name.lower()
            if item_lower == possible_item_2:
                found_items[item_name] = current_qty
                current_qty = 1 
                break 
            elif item_lower == possible_item_1:
                found_items[item_name] = current_qty
                current_qty = 1
                break
    if found_items:
        items_spoken = []
        for item, qty in found_items.items():
            shopping_cart[item] = shopping_cart.get(item, 0) + qty
            items_spoken.append(f"{qty} {item}")
        speak_text = f"Đã thêm {', '.join(items_spoken)} vào giỏ hàng."
        speak(speak_text)
        root.after(10, update_cart_summary)
        return
    else:
        print("Không tìm thấy lệnh đặt hàng, chuyển sang OpenAI...")
        if root: root.after(0, status_label.config, {"text": "Vâng, để tôi suy nghĩ...", "fg": "blue"})
        ai_response = get_openai_response(text)
        speak(ai_response)
        
def start_voice_thread():
    """Bắt đầu luồng lắng nghe (được gọi bởi nút bấm)."""
    global voice_button
    if voice_button: voice_button.config(state=tk.DISABLED, text="...")
    threading.Thread(target=voice_loop, daemon=True).start()
    
def voice_loop():
    """
    Hàm này chạy trong Thread. 
    Nó lắng nghe, sau đó xử lý, rồi kích hoạt lại nút.
    """
    text = listen()
    if text:
        process_voice_command(text)
    if root and voice_button: 
        root.after(10, lambda: voice_button.config(state=tk.NORMAL, text="🎙️ Nhấn để nói"))

def play_music_file(filename):
    """Hàm chuyên dùng để phát nhạc (không chặn giao diện)."""
    try:
        if not os.path.exists(filename):
            speak("Xin lỗi, tôi không tìm thấy file nhạc.")
            return

        # Dừng nhạc hoặc giọng nói đang phát (nếu có)
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        # Load và phát nhạc
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        # Không dùng pygame.time.wait() ở đây để Robot vẫn hoạt động được
        # trong lúc nhạc đang chạy nền.
        print(f"Đang phát nhạc: {filename}")
        
    except Exception as e:
        print(f"Lỗi phát nhạc: {e}")
        speak("Có lỗi khi mở nhạc.")

# --- CLASS TẠO NÚT BẤM BO GÓC (Dán vào phần Helper) ---
# ============================================================
# CLASS TẠO NÚT BẤM BO GÓC (ĐÃ FIX LỖI RĂNG CƯA/MÉO HÌNH)
# ============================================================
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=200, height=50, corner_radius=20, bg_color="#007BFF", fg_color="white", hover_color="#0056b3"):
        # highlightthickness=0 là quan trọng để xóa viền canvas mặc định
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=0)
        self.command = command
        self.text_str = text
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg_color = fg_color
        self.corner_radius = corner_radius

        # Sự kiện chuột (Bind vào chính Canvas để bắt sự kiện toàn vùng)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

        # Vẽ lần đầu
        self.draw(self.bg_color)

    def draw(self, color):
        self.delete("all") # Xóa hình cũ
        w = int(self["width"])
        h = int(self["height"])
        r = self.corner_radius
        
        # Kỹ thuật vẽ chồng hình (Shape merging) để tạo khối mượt mà:
        
        # 1. Vẽ 4 hình tròn ở 4 góc
        self.create_oval(0, 0, r*2, r*2, fill=color, outline="")       # Góc Trái-Trên
        self.create_oval(w-r*2, 0, w, r*2, fill=color, outline="")     # Góc Phải-Trên
        self.create_oval(0, h-r*2, r*2, h, fill=color, outline="")     # Góc Trái-Dưới
        self.create_oval(w-r*2, h-r*2, w, h, fill=color, outline="")   # Góc Phải-Dưới
        
        # 2. Vẽ 2 hình chữ nhật thân (ngang và dọc) đè lên để nối liền 4 góc
        self.create_rectangle(r, 0, w-r, h, fill=color, outline="")    # Thân dọc
        self.create_rectangle(0, r, w, h-r, fill=color, outline="")    # Thân ngang
        
        # 3. Vẽ chữ lên trên cùng
        self.create_text(w/2, h/2, text=self.text_str, fill=self.fg_color, font=("Arial", 14, "bold"))

    def on_enter(self, e):
        self.config(cursor="hand2") # Đổi con trỏ chuột thành bàn tay
        self.draw(self.hover_color) # Đổi màu nền hover

    def on_leave(self, e):
        self.draw(self.bg_color) # Trả lại màu cũ

    def on_click(self, e):
        # Hiệu ứng nhấn nút (Dịch chuyển nội dung xuống 1px)
        self.move("all", 1, 1)
        root.after(100, lambda: self.move("all", -1, -1))
        if self.command:
            self.command()
def main():
    # 1. Khai báo toàn bộ biến Global cần dùng
    global root, status_label, menu_frame, checkout_frame, payment_frame, idle_frame
    global cart_summary_label, checkout_details_label, qr_label
    global voice_button, keypad_frame, keypad_display_var, keypad_item_label
    global conversation_history, chat_system_prompt
    global shopping_cart, current_orderId, menu_items
    
    # 2. Tạo cửa sổ chính (Chỉ chạy 1 lần)
    root = tk.Tk()
    root.title("ROBOT PHỤC VỤ - HỆ THỐNG TỰ ĐỘNG")
    root.geometry("480x800") # Kích thước phù hợp màn hình dọc
    # root.attributes('-fullscreen', True) # Bỏ comment nếu muốn chạy full màn hình

    # 3. Tải Menu ngay khi khởi động
    if not load_menu_from_server():
        print("Cảnh báo: Không tải được menu lúc khởi động. Sẽ thử lại sau.")

    # --- TẠO MÀN HÌNH CHỜ (IDLE FRAME) ---
    idle_frame = tk.Frame(root, bg="white")
    tk.Label(idle_frame, text="( ^_^)／", font=("Arial", 60), bg="white", fg="#333").pack(pady=(100, 20))
    tk.Label(idle_frame, text="XIN CHÀO!", font=("Arial", 30, "bold"), bg="white", fg="#007BFF").pack(pady=10)
    tk.Label(idle_frame, text="Tôi đang đợi lệnh từ khách hàng...", font=("Arial", 14), bg="white", fg="gray").pack(pady=10)
    tk.Label(idle_frame, text="Vui lòng gọi món tại bàn", font=("Arial", 12, "italic"), bg="white", fg="#555").pack(side="bottom", pady=50)

    # --- LABEL TRẠNG THÁI CHUNG ---
    status_label = tk.Label(root, text="Hệ thống sẵn sàng", font=("Arial", 14), bg="#f0f0f0", fg="blue")
    status_label.pack(side="top", fill="x", pady=5)

    # ============================================================
    # KHỞI TẠO SẴN CÁC FRAME PHỤC VỤ
    # ============================================================

    # --- 1. MÀN HÌNH MENU (MENU FRAME) ---
    menu_frame = tk.Frame(root)
    
    cart_summary_label = tk.Label(menu_frame, text="Giỏ hàng trống", font=("Arial", 12, "italic"))
    cart_summary_label.pack(pady=10)

    # Frame lưới nút món ăn
    button_grid_frame = tk.Frame(menu_frame)
    button_grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
    button_grid_frame.configure(bg="#F5F5F5")

    MAX_COLUMNS = 2 
    current_row = 0
    current_col = 0
    item_list = list(menu_items.keys())

    # --- VÒNG LẶP TẠO THẺ SẢN PHẨM (Card) ---
    for item_name in item_list:
        item_data = menu_items[item_name] 
        price = item_data['price']
        img_url = item_data.get('image_url', "")
        
        if not img_url:
            for ext in [".png", ".jpg", ".jpeg"]:
                if os.path.exists(f"assets/{item_name}{ext}"):
                    img_url = f"assets/{item_name}{ext}"
                    break
        
        create_product_card(button_grid_frame, item_name, price, img_url, current_row, current_col)
        
        current_col += 1
        if current_col >= MAX_COLUMNS:
            current_col = 0
            current_row += 1

    for i in range(MAX_COLUMNS): button_grid_frame.columnconfigure(i, weight=1)

    # --- NÚT CHỨC NĂNG (ĐÃ LÀM ĐẸP) ---
    
    # Nút Thanh toán (Menu)
    checkout_btn = RoundedButton(
        menu_frame, 
        text="Thanh toán ngay", 
        width=350, height=60,
        bg_color="#00A000", hover_color="#008000",
        command=show_checkout_screen
    )
    checkout_btn.pack(pady=10)
    
    # Nút Voice (Giữ nguyên tk.Button vì cần đổi text động)
    voice_button = tk.Button(menu_frame, text="🎙️ Nhấn để nói", font=("Arial", 14), bg="#007BFF", fg="white", command=start_voice_thread)
    voice_button.pack(pady=10, fill="x", padx=40)

    # --- 2. MÀN HÌNH THANH TOÁN (CHECKOUT FRAME) ---
    checkout_frame = tk.Frame(root)
    checkout_details_label = tk.Label(checkout_frame, text="...", font=("Arial", 12), justify=tk.LEFT)
    checkout_details_label.pack(pady=20)
    
    # --- THAY THẾ CÁC NÚT BẰNG CLASS RoundedButton ---
    
    # 1. Nút Thanh toán QR (Màu Tím)
    btn_qr = RoundedButton(
        checkout_frame, 
        text="Thanh toán QR (Tự động)", 
        width=350, height=60, 
        bg_color="#AA00AA", hover_color="#880088", 
        command=handle_qr_payment
    )
    btn_qr.pack(pady=15)

    # 2. Nút Thanh toán tại quầy (Màu Xanh Lá)
    btn_cash = RoundedButton(
        checkout_frame, 
        text="Thanh toán tại quầy", 
        width=350, height=60,
        bg_color="#008B8B", hover_color="#006666", # Màu Cyan đậm
        command=handle_cash_payment
    )
    btn_cash.pack(pady=15)

    # 3. Nút Quay lại (Màu Cam)
    btn_back = RoundedButton(
        checkout_frame, 
        text="Quay lại chọn món", 
        width=350, height=50,
        bg_color="#FF5722", hover_color="#E64A19", 
        command=show_menu_screen
    )
    btn_back.pack(pady=20)

    # --- 3. MÀN HÌNH QUÉT MÃ (PAYMENT FRAME) ---
    payment_frame = tk.Frame(root)
    qr_label = tk.Label(payment_frame)
    qr_label.pack(pady=20)
    
    # Nút Hủy bỏ (Màu Đỏ)
    btn_cancel = RoundedButton(
        payment_frame, 
        text="Hủy bỏ", 
        width=200, height=50,
        bg_color="#DD0000", hover_color="#AA0000", 
        command=reset_kiosk
    )
    btn_cancel.pack(pady=20)

    # --- 4. MÀN HÌNH BÀN PHÍM SỐ (KEYPAD FRAME) ---
    keypad_frame = tk.Frame(root)
    keypad_display_var = tk.StringVar()
    
    keypad_item_label = tk.Label(keypad_frame, text="Nhập số lượng:", font=("Arial", 16, "bold"))
    keypad_item_label.pack(pady=20)
    
    tk.Label(keypad_frame, textvariable=keypad_display_var, font=("Arial", 30, "bold"), bg="white", width=10, relief="sunken").pack(pady=10)
    
    keypad_buttons_frame = tk.Frame(keypad_frame)
    keypad_buttons_frame.pack(pady=10)
    
    # Logic nút số (Giữ nguyên tk.Button vì cần Grid chính xác)
    btn_font = ("Arial", 18, "bold"); w=5; h=2
    # Hàng 1
    tk.Button(keypad_buttons_frame, text="1", font=btn_font, width=w, height=h, command=lambda: keypad_press(1)).grid(row=0, column=0, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="2", font=btn_font, width=w, height=h, command=lambda: keypad_press(2)).grid(row=0, column=1, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="3", font=btn_font, width=w, height=h, command=lambda: keypad_press(3)).grid(row=0, column=2, padx=5, pady=5)
    # Hàng 2
    tk.Button(keypad_buttons_frame, text="4", font=btn_font, width=w, height=h, command=lambda: keypad_press(4)).grid(row=1, column=0, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="5", font=btn_font, width=w, height=h, command=lambda: keypad_press(5)).grid(row=1, column=1, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="6", font=btn_font, width=w, height=h, command=lambda: keypad_press(6)).grid(row=1, column=2, padx=5, pady=5)
    # Hàng 3
    tk.Button(keypad_buttons_frame, text="7", font=btn_font, width=w, height=h, command=lambda: keypad_press(7)).grid(row=2, column=0, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="8", font=btn_font, width=w, height=h, command=lambda: keypad_press(8)).grid(row=2, column=1, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="9", font=btn_font, width=w, height=h, command=lambda: keypad_press(9)).grid(row=2, column=2, padx=5, pady=5)
    # Hàng 4
    tk.Button(keypad_buttons_frame, text="XÓA", font=btn_font, width=w, height=h, bg="#FFCC00", command=keypad_clear).grid(row=3, column=0, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="0", font=btn_font, width=w, height=h, command=lambda: keypad_press(0)).grid(row=3, column=1, padx=5, pady=5)
    tk.Button(keypad_buttons_frame, text="OK", font=btn_font, width=w, height=h, bg="#00A000", fg="white", command=keypad_enter).grid(row=3, column=2, padx=5, pady=5)
    
    # Nút Quay lại (Keypad) - Làm đẹp
    btn_keypad_back = RoundedButton(
        keypad_frame, 
        text="QUAY LẠI", 
        width=200, height=50,
        bg_color="#DD0000", hover_color="#AA0000",
        command=keypad_cancel
    )
    btn_keypad_back.pack(pady=20)

    # ============================================================
    # BẮT ĐẦU CHƯƠNG TRÌNH
    # ============================================================
    
    show_idle_screen()
    check_for_new_orders()
    
    print("🚀 Hệ thống Robot đã khởi động. Đang chờ lệnh...")
    root.mainloop()

# --- HÀM MỚI: VÒNG LẶP CHỜ CỦA ROBOT ---
# --- SỬA HÀM NÀY ---
def robot_idle_loop():
    print("🤖 Robot đang ở chế độ chờ, bắt đầu poll API...")
    
    if not load_menu_from_server():
        print("Không tải được menu, thử lại sau...")
    
    while True: # Vòng lặp vô tận trên MAIN THREAD
        try:
            # ... (Phần gọi API giữ nguyên) ...
            url = f"{HEROKU_APP_URL}/api/get-service-requests"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                requests_list = response.json()
                
                if requests_list:
                    service_req = requests_list[0]
                    table = service_req.get('table_number')
                    req_id = service_req.get('request_id')
                    
                    print(f"🔔 CÓ LỆNH MỚI! Đi đến Bàn {table}")
                    
                    # Báo cáo đã nhận lệnh (Giữ nguyên code của bạn)
                    try:
                        requests.post(f"{HEROKU_APP_URL}/api/complete-service-request/{req_id}", timeout=5)
                    except:
                        pass
                    
                    # --- KHỞI ĐỘNG GIAO DIỆN ---
                    print("Mở giao diện phục vụ...")
                    
                    # Hàm main() sẽ chạy và CHẶN (block) tại đây cho đến khi finish_and_go_home() được gọi
                    main(table_number=table, request_id=req_id)
                    
                    # KHI main() KẾT THÚC (do finish_and_go_home đóng cửa sổ), code sẽ chạy tiếp xuống đây
                    print("Giao diện đã đóng. Robot quay lại trạng thái chờ (Idle)...")
                    
                    # Vòng lặp while True sẽ tự động lặp lại -> Poll tiếp
                    
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Đang chờ khách gọi...", end='\r')
                    time.sleep(5)
            else:
                time.sleep(5)
                
        except Exception as e:
            print(f"Lỗi trong vòng lặp chờ: {e}")
            time.sleep(10)


# --- MODIFIED: ĐIỂM BẮT ĐẦU CỦA CHƯƠNG TRÌNH ---
if __name__ == "__main__":
    main()