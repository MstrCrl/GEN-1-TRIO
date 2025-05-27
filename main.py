import pygame
from pygame.locals import *
from OpenGL.GL import *
import glm
import numpy as np
import ctypes
import config
from model_loader import load_model_from_txt
from texture_loader import load_texture
from shader import create_shader_program
from bg_loader import create_bg_shader_program


def main():
    pygame.init()
    display = (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption(config.WINDOW_TITLE)

    glEnable(GL_DEPTH_TEST)

    # Load background image as OpenGL texture
    bg_surface = pygame.image.load("source/bg.jpg").convert_alpha()
    bg_width, bg_height = bg_surface.get_size()
    bg_data = pygame.image.tostring(bg_surface, "RGBA", True)

    bg_texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, bg_texture)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, bg_width, bg_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, bg_data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glBindTexture(GL_TEXTURE_2D, 0)

    bg_shader_program = create_bg_shader_program()

    # Setup fullscreen quad for background
    quad_vertices = np.array([
        -1.0,  1.0,    0.0, 1.0,
        -1.0, -1.0,    0.0, 0.0,
         1.0, -1.0,    1.0, 0.0,
        -1.0,  1.0,    0.0, 1.0,
         1.0, -1.0,    1.0, 0.0,
         1.0,  1.0,    1.0, 1.0
    ], dtype=np.float32)

    bg_VAO = glGenVertexArrays(1)
    bg_VBO = glGenBuffers(1)

    glBindVertexArray(bg_VAO)
    glBindBuffer(GL_ARRAY_BUFFER, bg_VBO)
    glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)

    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * quad_vertices.itemsize, ctypes.c_void_p(0))
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * quad_vertices.itemsize, ctypes.c_void_p(2 * quad_vertices.itemsize))

    glBindBuffer(GL_ARRAY_BUFFER, 0)
    glBindVertexArray(0)

    # Load 3D model objects
    shader_program = create_shader_program()
    glUseProgram(shader_program)
    objects = load_model_from_txt("materials", load_texture)

    projection = glm.perspective(glm.radians(config.FOV), display[0] / display[1], config.NEAR_PLANE, config.FAR_PLANE)
    view = glm.lookAt(config.CAMERA_POS, config.CAMERA_TARGET, config.CAMERA_UP)

    proj_loc = glGetUniformLocation(shader_program, "projection")
    view_loc = glGetUniformLocation(shader_program, "view")
    model_loc = glGetUniformLocation(shader_program, "model")

    glUniformMatrix4fv(proj_loc, 1, GL_FALSE, glm.value_ptr(projection))
    glUniformMatrix4fv(view_loc, 1, GL_FALSE, glm.value_ptr(view))

    # Camera and rotation state
    camera_distance = 30
    rot_x, rot_y = 62, 105
    last_mouse_pos = (0, 0)
    mouse_down = False

    clock = pygame.time.Clock()
    running = True

    while running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    view_info = f"Zoom: {camera_distance:.2f}, rot_x: {rot_x:.2f}, rot_y: {rot_y:.2f}"
                    print(view_info)
                    with open("view_log.txt", "a") as log:
                        log.write(view_info + "\n")
                    print("Saved to view_log.txt")
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:
                    camera_distance = max(1.0, camera_distance - 0.5)
                elif event.button == 5:
                    camera_distance += 0.5
                if event.button == 1:
                    mouse_down = True
                    last_mouse_pos = pygame.mouse.get_pos()
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    mouse_down = False
            if event.type == pygame.MOUSEMOTION and mouse_down:
                x, y = pygame.mouse.get_pos()
                dx = x - last_mouse_pos[0]
                dy = y - last_mouse_pos[1]
                rot_y += dx * 0.5
                rot_x += dy * 0.5
                last_mouse_pos = (x, y)

        # --- Render background ---
        glClear(GL_COLOR_BUFFER_BIT)
        glDisable(GL_DEPTH_TEST)

        glUseProgram(bg_shader_program)
        glBindVertexArray(bg_VAO)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, bg_texture)
        bg_tex_loc = glGetUniformLocation(bg_shader_program, "backgroundTexture")
        glUniform1i(bg_tex_loc, 0)
        glDrawArrays(GL_TRIANGLES, 0, 6)

        glBindTexture(GL_TEXTURE_2D, 0)
        glBindVertexArray(0)

        # --- Render 3D scene ---
        glEnable(GL_DEPTH_TEST)
        glClear(GL_DEPTH_BUFFER_BIT)

        view = glm.lookAt(glm.vec3(0, camera_distance, 0), config.CAMERA_TARGET, config.CAMERA_UP)
        glUseProgram(shader_program)
        glUniformMatrix4fv(view_loc, 1, GL_FALSE, glm.value_ptr(view))

        time = pygame.time.get_ticks() / 1000.0  # Seconds

        for obj in objects:
            model_matrix = glm.mat4(1.0)
            model_matrix = glm.rotate(model_matrix, glm.radians(rot_x), glm.vec3(1, 0, 0))
            model_matrix = glm.rotate(model_matrix, glm.radians(rot_y), glm.vec3(0, 1, 0))

            exclude_names = ["Grass", "Stage", "Rock", "Grass.001", "Grass.002", "Grass.003", "Grass.004", "Grass.005", "Grass.006"]
            if not any(name in obj.name for name in exclude_names):
                bounce = 0.03 * glm.sin(time * 4.0)
                model_matrix = glm.translate(model_matrix, glm.vec3(0, bounce, 0))

            glUniformMatrix4fv(model_loc, 1, GL_FALSE, glm.value_ptr(model_matrix))
            obj.draw(shader_program, config.TEXTURE_UNITS)

        pygame.display.flip()

    # Cleanup
    for obj in objects:
        glDeleteVertexArrays(1, [obj.VAO])
        glDeleteBuffers(1, [obj.VBO])
        glDeleteBuffers(1, [obj.EBO])
        for tex_id in obj.textures.values():
            glDeleteTextures(1, [tex_id])

    glDeleteVertexArrays(1, [bg_VAO])
    glDeleteBuffers(1, [bg_VBO])
    glDeleteTextures(1, [bg_texture])

    glDeleteProgram(bg_shader_program)
    glDeleteProgram(shader_program)
    pygame.quit()


if __name__ == "__main__":
    main()
