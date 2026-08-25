from pathlib import Path
import threading
import time
import ctypes

import pygame
import live2d.v3 as live2d
from OpenGL import GL


class AvatarRenderer:
    """
    Renderer Live2D para Windows.

    Recursos:
    - Live2D Cubism
    - pygame + OpenGL
    - janela sem moldura
    - fundo transparente via color key
    - escala proporcional
    - motions
    - estados do avatar
    """

    WIDTH = 700
    HEIGHT = 800
    FPS = 60

    # Cor usada como fundo transparente.
    # Magenta forte para não conflitar com a Miku.
    TRANSPARENT_COLOR = (0, 0, 0)

    def __init__(self, model_path: str):

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelo do avatar não encontrado: {self.model_path}"
            )

        self.running = False
        self.initialized = False

        self.window = None
        self.model = None
        self.hwnd = None

        self.thread = None

        self.status = "idle"
        self.expression = "neutral"
        self.intensity = 1.0

        # Estado do arrasto da janela (clique e segure para mover).
        self._dragging = False
        self._drag_offset = (0, 0)

        self._lock = threading.Lock()

    # ==========================================================
    # START
    # ==========================================================

    def start(self):

        if self.running:
            return

        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
        )

        self.thread.start()

        timeout = time.time() + 10

        while (
            not self.initialized
            and time.time() < timeout
        ):
            time.sleep(0.01)

        if not self.initialized:
            self.running = False

            raise RuntimeError(
                "O renderer Live2D não conseguiu inicializar."
            )

    # ==========================================================
    # RENDER LOOP
    # ==========================================================

    def _run(self):

        try:

            # --------------------------------------------------
            # Pygame
            # --------------------------------------------------

            pygame.init()

            flags = (
                pygame.DOUBLEBUF
                | pygame.OPENGL
                | pygame.NOFRAME
            )

            self.window = pygame.display.set_mode(
                (
                    self.WIDTH,
                    self.HEIGHT,
                ),
                flags,
            )

            pygame.display.set_caption(
                "Agente Pessoal"
            )

            # --------------------------------------------------
            # Inicializa Live2D
            # --------------------------------------------------

            live2d.init()
            live2d.glInit()
            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)

            print(
                "[AvatarRenderer] Carregando:",
                self.model_path,
            )

            self.model = live2d.LAppModel()

            self.model.LoadModelJson(
                str(self.model_path)
            )

            print(
                "[AvatarRenderer] "
                "Modelo Live2D carregado."
            )

            # --------------------------------------------------
            # ESCALA PROPORCIONAL
            # --------------------------------------------------

            self.model.SetScale(0.72)

            # X / Y uniforme.
            # Evita esticar o personagem.

            self.model.SetOffset(
                0.0,
                -0.05,
            )

            # --------------------------------------------------
            # MOTION INICIAL
            # --------------------------------------------------

            try:

                self.model.StartRandomMotion(
                    "Idle",
                    1,
                )

            except Exception as error:

                print(
                    "[AvatarRenderer] "
                    f"Não foi possível iniciar Idle: {error}"
                )

            # --------------------------------------------------
            # CONFIGURA TRANSPARÊNCIA WINDOWS
            # --------------------------------------------------

            self._configure_transparent_window()

            self.initialized = True

            clock = pygame.time.Clock()

            # ==================================================
            # LOOP
            # ==================================================

            while self.running:

                for event in pygame.event.get():

                    if event.type == pygame.QUIT:

                        self.running = False
                        break

                    if event.type == pygame.KEYDOWN:

                        if event.key == pygame.K_ESCAPE:

                            self.running = False
                            break

                    if event.type == pygame.MOUSEMOTION:
                        if self._dragging:
                            self._drag_window()
                        else:
                            self._handle_mouse_motion(event.pos)

                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            self._start_window_drag()

                    if event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            self._dragging = False

                if not self.running:
                    break

                # ------------------------------------------------
                # UPDATE
                # ------------------------------------------------

                # Nota: em algumas versões da lib live2d-py, Update()
                # não aceita deltaTimeSeconds e calcula o tempo
                # internamente. Se a sua versão exigir o parâmetro,
                # troque para: self.model.Update(clock.get_time() / 1000.0)

                try:

                    self.model.Update()

                except Exception as error:

                    print(
                        "[AvatarRenderer] "
                        f"Erro no Update: {error}"
                    )

                # ------------------------------------------------
                # FUNDO MAGENTA
                # ------------------------------------------------

                # A janela do Windows transforma essa cor
                # em transparente.

                r, g, b = self.TRANSPARENT_COLOR

                try:

                    live2d.clearBuffer(
                        r / 255.0,
                        g / 255.0,
                        b / 255.0,
                        0.0,
                    )

                except Exception:

                    # Fallback para versões que não aceitam alpha.
                    live2d.clearBuffer(
                        r / 255.0,
                        g / 255.0,
                        b / 255.0,
                    )

                # ------------------------------------------------
                # DESENHA MODELO
                # ------------------------------------------------

                try:

                    self.model.Draw()

                except Exception as error:

                    print(
                        "[AvatarRenderer] "
                        f"Erro no Draw: {error}"
                    )

                pygame.display.flip()

                clock.tick(self.FPS)

        except Exception as error:

            print(
                "[AvatarRenderer] ERRO FATAL:"
            )

            print(error)

            self.initialized = False

        finally:

            self._shutdown()

    def _handle_mouse_motion(self, position):
        if self.model is None:
            return

        mouse_x, mouse_y = position

        # Normaliza X para o intervalo [-1.0, 1.0]
        norm_x = (mouse_x / self.WIDTH) * 2.0 - 1.0

        # Normaliza Y para o intervalo [-1.0, 1.0] (invertendo o eixo Y do Pygame)
        norm_y = 1.0 - (mouse_y / self.HEIGHT) * 2.0

        try:
            # Drag() já atualiza para onde o modelo deve "olhar"/arrastar.
            # Não existe SetTarget() nesta versão da lib live2d-py.
            self.model.Drag(norm_x, norm_y)
        except Exception as error:
            print(f"[AvatarRenderer] Erro ao mover o modelo com o mouse: {error}")

    # ==========================================================
    # ARRASTAR A JANELA (a janela não tem borda/título)
    # ==========================================================

    def _start_window_drag(self):
        """Chamado ao pressionar o botão esquerdo do mouse."""

        if self.hwnd is None:
            return

        try:
            import win32gui

            cursor_x, cursor_y = win32gui.GetCursorPos()
            window_left, window_top, _, _ = win32gui.GetWindowRect(self.hwnd)

            self._drag_offset = (
                cursor_x - window_left,
                cursor_y - window_top,
            )

            self._dragging = True

        except Exception as error:
            print(f"[AvatarRenderer] Erro ao iniciar arrasto: {error}")

    def _drag_window(self):
        """Chamado a cada movimento do mouse enquanto o botão está preso."""

        if self.hwnd is None:
            return

        try:
            import win32gui
            import win32con

            cursor_x, cursor_y = win32gui.GetCursorPos()
            offset_x, offset_y = self._drag_offset

            new_x = cursor_x - offset_x
            new_y = cursor_y - offset_y

            win32gui.SetWindowPos(
                self.hwnd,
                None,
                new_x,
                new_y,
                0,
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOZORDER,
            )

        except Exception as error:
            print(f"[AvatarRenderer] Erro ao arrastar janela: {error}")

    # ==========================================================
    # WINDOWS TRANSPARENT WINDOW
    # ==========================================================

    def _configure_transparent_window(self):

        if self.window is None:
            return

        try:

            import win32gui
            import win32con

        except ImportError:

            print(
                "[AvatarRenderer] "
                "pywin32 não instalado."
            )

            print(
                "Execute: pip install pywin32"
            )

            return

        hwnd = pygame.display.get_wm_info()["window"]
        self.hwnd = hwnd

        # ------------------------------------------------------
        # Remove borda / título
        # ------------------------------------------------------

        style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_STYLE,
        )

        style &= ~win32con.WS_CAPTION
        style &= ~win32con.WS_THICKFRAME
        style &= ~win32con.WS_MINIMIZE
        style &= ~win32con.WS_MAXIMIZE
        style &= ~win32con.WS_SYSMENU

        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_STYLE,
            style,
        )

        # ------------------------------------------------------
        # Adiciona Layered Window
        # ------------------------------------------------------

        ex_style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
        )

        ex_style |= win32con.WS_EX_LAYERED

        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style,
        )

        # ------------------------------------------------------
        # Color Key
        # ------------------------------------------------------

        color = (
            self.TRANSPARENT_COLOR[0]
            | (
                self.TRANSPARENT_COLOR[1]
                << 8
            )
            | (
                self.TRANSPARENT_COLOR[2]
                << 16
            )
        )

        ctypes.windll.user32.SetLayeredWindowAttributes(
            hwnd,
            color,
            0,
            win32con.LWA_COLORKEY,
        )

        # ------------------------------------------------------
        # Mantém janela no topo
        # ------------------------------------------------------

        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            100,
            100,
            self.WIDTH,
            self.HEIGHT,
            win32con.SWP_SHOWWINDOW,
        )

        print(
            "[AvatarRenderer] "
            "Janela transparente configurada."
        )

    # ==========================================================
    # STATUS
    # ==========================================================

    def set_status(self, status: str):

        if not self.running:
            return

        with self._lock:

            self.status = status

        print(
            f"[AvatarRenderer] Status: {status}"
        )

        self._play_status_motion(
            status
        )

    # ==========================================================
    # EXPRESSIONS
    # ==========================================================

    def set_expression(
        self,
        expression: str,
        intensity: float = 1.0,
    ):

        if not self.running:
            return

        intensity = max(
            0.0,
            min(1.0, intensity),
        )

        with self._lock:

            self.expression = expression
            self.intensity = intensity

        print(
            "[AvatarRenderer] "
            f"Expression: {expression} "
            f"({intensity:.2f})"
        )

        self._play_expression_motion(
            expression
        )

    # ==========================================================
    # STATUS MOTIONS
    # ==========================================================

    def _play_status_motion(
        self,
        status: str,
    ):

        if self.model is None:
            return

        try:

            if status == "idle":

                self.model.StartRandomMotion(
                    "Idle",
                    1,
                )

            elif status == "thinking":

                self.model.StartRandomMotion(
                    "Tap",
                    1,
                )

            elif status == "listening":

                self.model.StartRandomMotion(
                    "Flick",
                    1,
                )

            elif status == "speaking":

                self.model.StartRandomMotion(
                    "Tap",
                    1,
                )

        except Exception as error:

            print(
                "[AvatarRenderer] "
                f"Erro motion {status}: {error}"
            )

    # ==========================================================
    # EXPRESSIONS
    # ==========================================================

    def _play_expression_motion(
        self,
        expression: str,
    ):

        if self.model is None:
            return

        try:

            if expression == "happy":

                self.model.StartRandomMotion(
                    "Tap",
                    2,
                )

            elif expression == "sad":

                self.model.StartRandomMotion(
                    "Flick",
                    1,
                )

            elif expression == "angry":

                self.model.StartRandomMotion(
                    "Flick3",
                    2,
                )

            elif expression == "surprised":

                self.model.StartRandomMotion(
                    "Tap",
                    2,
                )

            elif expression == "thinking":

                self.model.StartRandomMotion(
                    "Tap",
                    1,
                )

        except Exception as error:

            print(
                "[AvatarRenderer] "
                f"Erro expressão {expression}: {error}"
            )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(self):

        self.running = False

        if self.thread:

            self.thread.join(
                timeout=3
            )

            self.thread = None

    # ==========================================================
    # SHUTDOWN
    # ==========================================================

    def _shutdown(self):

        self.initialized = False

        try:

            live2d.dispose()

        except Exception:
            pass

        try:

            pygame.quit()

        except Exception:
            pass

        self.window = None
        self.model = None

        print(
            "[AvatarRenderer] "
            "Renderer encerrado."
        )

    # ==========================================================
    # STATE
    # ==========================================================

    def is_running(self):

        return self.running