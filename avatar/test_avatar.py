import time

from .avatar import Avatar


def main():
    avatar = Avatar()

    print()
    print("========================================")
    print("        LIVE2D AVATAR TEST")
    print("========================================")
    print()

    print("Modelo:")
    print(avatar.model_path)

    avatar.start()

    # Aguarda o renderer realmente abrir.
    time.sleep(1)

    print()
    print("Estado inicial:")
    print(avatar.state)

    # ------------------------------------------------------------
    # IDLE
    # ------------------------------------------------------------

    avatar.idle()

    print()
    print("Avatar em IDLE.")
    print("A janela deve permanecer aberta.")

    time.sleep(3)

    # ------------------------------------------------------------
    # THINKING
    # ------------------------------------------------------------

    print("Pensando...")
    avatar.thinking()

    time.sleep(3)

    # ------------------------------------------------------------
    # HAPPY
    # ------------------------------------------------------------

    print("Feliz...")
    avatar.happy(1.0)

    time.sleep(3)

    # ------------------------------------------------------------
    # SPEAKING
    # ------------------------------------------------------------

    print("Falando...")
    avatar.speaking()

    time.sleep(5)

    # ------------------------------------------------------------
    # SAD
    # ------------------------------------------------------------

    print("Triste...")
    avatar.sad(1.0)

    time.sleep(3)

    # ------------------------------------------------------------
    # SURPRISED
    # ------------------------------------------------------------

    print("Surpresa...")
    avatar.surprised(1.0)

    time.sleep(3)

    # ------------------------------------------------------------
    # ANGRY
    # ------------------------------------------------------------

    print("Bravo...")
    avatar.angry(1.0)

    time.sleep(3)

    # ------------------------------------------------------------
    # VOLTA PARA IDLE
    # ------------------------------------------------------------

    print("Voltando para IDLE...")
    avatar.neutral()
    avatar.idle()

    print()
    print("========================================")
    print("Pressione ESC ou feche a janela.")
    print("========================================")

    try:
        while avatar.renderer.is_running():
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass

    finally:
        avatar.close()

    print("Avatar encerrado.")


if __name__ == "__main__":
    main()