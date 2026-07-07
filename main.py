import json
import threading
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.video import Video
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.clock import Clock
import paho.mqtt.client as mqtt

# Название комнаты должно строго совпадать с вашим пультом на ПК!
CINEMA_ROOM = "love_cinema_room_secret_999"

MQTT_BROKER, MQTT_PORT = "broker.emqx.io", 1883
TOPIC_CONTROL = f"my_cinema/{CINEMA_ROOM}/control"

class CinemaPlayerLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        
        # Информационная надпись в режиме ожидания
        self.info_label = Label(
            text="🎬 ОЖИДАНИЕ СИГНАЛА ОТ ЛЮБИМОГО ХОСТА...",
            font_size='20sp',
            color=(0.54, 0.7, 0.98, 1)
        )
        self.add_widget(self.info_label)
        
        self.video_player = None
        self.controls_layout = None
        self.updating_slider = False
    def load_new_video(self, url):
        """Полностью очищает старый экран и загружает новую ссылку на фильм вместе с пультом управления"""
        # Удаляем старый плеер и пульт, если они были
        if self.video_player: self.remove_widget(self.video_player)
        if self.controls_layout: self.remove_widget(self.controls_layout)
        if self.info_label in self.children: self.remove_widget(self.info_label)

        # 1. Создаем встроенный видеоплеер Kivy
        self.video_player = Video(source=url, state='play', options={'eos': 'stop'})
        self.add_widget(self.video_player)

        # 2. Создаем красивую нижнюю панель управления для девушки
        self.controls_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=10, padding=10)
        
        # Кнопка Плей/Пауза для пульта проектора
        self.play_pause_btn = Button(text="⏸ ПАУЗА", size_hint_x=0.2, font_size='14sp')
        self.play_pause_btn.bind(on_press=self.local_toggle_play)
        self.controls_layout.add_widget(self.play_pause_btn)
        
        # Ползунок перемотки (Слайдер)
        self.seeker = Slider(min=0, max=100, value=0, size_hint_x=0.8)
        self.seeker.bind(on_touch_down=self.on_seeker_touch, on_touch_up=self.on_seeker_release)
        self.controls_layout.add_widget(self.seeker)
        
        self.add_widget(self.controls_layout)
        
        # Запускаем ежесекундное обновление ползунка времени
        Clock.schedule_interval(self.update_seeker, 1)

    def local_toggle_play(self, instance):
        """Локальное управление: девушка сама может нажать Плей/Паузу на проекторе"""
        if self.video_player:
            if self.video_player.state == 'play':
                self.video_player.state = 'pause'
                self.play_pause_btn.text = "▶ ПЛЕЙ"
            else:
                self.video_player.state = 'play'
                self.play_pause_btn.text = "⏸ ПАУЗА"

    def update_seeker(self, dt):
        """Обновляет положение ползунка в зависимости от текущего времени фильма"""
        if self.video_player and self.video_player.duration > 0 and not self.updating_slider:
            self.seeker.max = self.video_player.duration
            self.seeker.value = self.video_player.position

    def on_seeker_touch(self, instance, touch):
        if self.seeker.collide_point(*touch.pos):
            self.updating_slider = True

    def on_seeker_release(self, instance, touch):
        if self.updating_slider:
            if self.video_player and self.video_player.duration > 0:
                # Перематываем видео на то место, куда девушка перетащила ползунок
                self.video_player.seek(self.seeker.value / self.video_player.duration)
            self.updating_slider = False
    def control_playback(self, action):
        """Управляет воспроизведением на расстоянии (команды от вас)"""
        if self.video_player:
            if action == "play":
                self.video_player.state = 'play'
                self.play_pause_btn.text = "⏸ ПАУЗА"
            elif action == "pause":
                self.video_player.state = 'pause'
                self.play_pause_btn.text = "▶ ПЛЕЙ"

class AndroidCinemaApp(App):
    def build(self):
        self.layout = CinemaPlayerLayout()
        try: self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError: self.client = mqtt.Client()
        self.client.on_connect, self.client.on_message = self.on_connect, self.on_message
        threading.Thread(target=self.connect_mqtt, daemon=True).start()
        return self.layout

    def connect_mqtt(self):
        while True:
            try: self.client.connect(MQTT_BROKER, MQTT_PORT, 60); self.client.loop_forever()
            except: time.sleep(3)

    def on_connect(self, client, userdata, flags, rc):
        self.client.subscribe(TOPIC_CONTROL)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            action, url = data.get("action"), data.get("url", "")
            if action == "load" and url:
                Clock.schedule_once(lambda dt: self.layout.load_new_video(url))
            elif action in ["play", "pause"]:
                Clock.schedule_once(lambda dt: self.layout.control_playback(action))
        except: pass

if __name__ == "__main__":
    AndroidCinemaApp().run()
