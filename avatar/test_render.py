import os
import random
import pygame
from pygame.locals import DOUBLEBUF, OPENGL

import live2d.v3 as live2d


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "miku_free",
    "runtime",
    "miku.model3.json",
)


WIDTH = 700
HEIGHT = 900


def main():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Modelo não encontrado:\n{MODEL_PATH}"
        )

    print(f"[Avatar] Modelo: {MODEL_PATH}")

    pygame.init()

    pygame.display.set_mode(
        (WIDTH, HEIGHT),
        DOUBLEBUF | OPENGL,
    )

    pygame.display.set_caption(
        "Agente Pessoal — Avatar"
    )

    live2d.init()
    live2d.glInit()

    model = live2d.LAppModel()

    print("[Avatar] Carregando modelo...")

    model.LoadModelJson(
        MODEL_PATH,
        maskBufferCount=2,
    )

    model.Resize(WIDTH, HEIGHT)

    # ---------------------------------------------------------
    # CONFIGURAÇÕES NATURAIS
    # ---------------------------------------------------------

    model.SetAutoBlinkEnable(True)
    model.SetAutoBreathEnable(True)

    print(
        f"[Avatar] Parâmetros: "
        f"{model.GetParameterCount()}"
    )

    print("[Avatar] Modelo carregado.")
    print()
    print("Controles:")
    print("  ESC       -> sair")
    print("  SPACE     -> expressão aleatória")
    print("  M         -> motion aleatório")
    print("  R         -> reset")
    print("  1         -> expressão 1")
    print("  2         -> expressão 2")
    print("  3         -> expressão 3")
    print("  4         -> expressão 4")
    print("  B         -> respirar")
    print()

    clock = pygame.time.Clock()

    running = True

    # Controle simples de movimento automático
    next_motion = pygame.time.get_ticks() + 4000

    # ---------------------------------------------------------
    # LOOP
    # ---------------------------------------------------------

    while running:

        current_time = pygame.time.get_ticks()

        for event in pygame.event.get():

            # -------------------------------------------------
            # FECHAR
            # -------------------------------------------------

            if event.type == pygame.QUIT:
                running = False

            # -------------------------------------------------
            # TECLADO
            # -------------------------------------------------

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                # ---------------------------------------------
                # EXPRESSÃO ALEATÓRIA
                # ---------------------------------------------

                elif event.key == pygame.K_SPACE:
                    print("[Avatar] Nova expressão")

                    try:
                        model.SetRandomExpression()
                    except Exception as error:
                        print(
                            f"[Avatar] Erro expressão: {error}"
                        )

                # ---------------------------------------------
                # MOTION ALEATÓRIO
                # ---------------------------------------------

                elif event.key == pygame.K_m:
                    print("[Avatar] Novo motion")

                    try:
                        model.StartRandomMotion(
                            priority=3
                        )
                    except Exception as error:
                        print(
                            f"[Avatar] Erro motion: {error}"
                        )

                # ---------------------------------------------
                # RESET
                # ---------------------------------------------

                elif event.key == pygame.K_r:
                    print("[Avatar] Reset")

                    try:
                        model.StopAllMotions()
                    except Exception:
                        pass

                    try:
                        model.ResetPose()
                    except Exception:
                        pass

                    try:
                        model.ResetExpression()
                    except Exception:
                        pass

                # ---------------------------------------------
                # EXPRESSÕES MANUAIS
                # ---------------------------------------------

                elif event.key in (
                    pygame.K_1,
                    pygame.K_2,
                    pygame.K_3,
                    pygame.K_4,
                ):
                    expression_index = (
                        event.key - pygame.K_1
                    )

                    print(
                        "[Avatar] Expressão:",
                        expression_index,
                    )

                    try:
                        model.SetExpression(
                            expression_index
                        )
                    except Exception as error:
                        print(
                            "[Avatar] "
                            f"Erro expressão: {error}"
                        )

                # ---------------------------------------------
                # RESPIRAÇÃO
                # ---------------------------------------------

                elif event.key == pygame.K_b:
                    print(
                        "[Avatar] Respiração automática"
                    )

                    try:
                        model.SetAutoBreathEnable(
                            True
                        )
                    except Exception:
                        pass

            # -------------------------------------------------
            # MOUSE
            # -------------------------------------------------

            elif event.type == pygame.MOUSEMOTION:

                mouse_x, mouse_y = event.pos

                # Normaliza para -1 até +1
                x = (
                    (mouse_x / WIDTH) * 2
                ) - 1

                y = (
                    (mouse_y / HEIGHT) * 2
                ) - 1

                try:
                    model.SetDragging(
                        x,
                        y,
                    )
                except Exception:
                    pass

        # -----------------------------------------------------
        # MOTIONS AUTOMÁTICOS
        # -----------------------------------------------------

        if current_time >= next_motion:

            try:
                model.StartRandomMotion(
                    priority=2
                )

                print(
                    "[Avatar] Motion automático"
                )

            except Exception as error:
                print(
                    "[Avatar] "
                    f"Erro no motion automático: {error}"
                )

            next_motion = (
                current_time
                + random.randint(
                    5000,
                    9000,
                )
            )

        # -----------------------------------------------------
        # UPDATE
        # -----------------------------------------------------

        model.Update()

        # -----------------------------------------------------
        # FUNDO
        # -----------------------------------------------------

        live2d.clearBuffer(
            0.08,
            0.08,
            0.10,
            1.0,
        )

        # -----------------------------------------------------
        # DESENHAR MODELO
        # -----------------------------------------------------

        model.Draw()

        pygame.display.flip()

        clock.tick(60)

    # ---------------------------------------------------------
    # ENCERRAMENTO
    # ---------------------------------------------------------

    print("[Avatar] Encerrando...")

    try:
        live2d.dispose()
    except Exception:
        pass

    pygame.quit()


if __name__ == "__main__":
    main()