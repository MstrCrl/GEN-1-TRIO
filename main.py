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
    # Initialize pygame and its mixer (audio)
    pygame.init()
    pygame.mixer.init()

    # Setup display window with OpenGL context
    display = (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption(config.WINDOW_TITLE)

    # Enable depth test for proper 3D rendering
    glEnable(GL_DEPTH_TEST)

    # Load background image and create OpenGL texture for it
    bg_surface = pygame.image.load("source/image.jpg").convert_alpha()
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

    # Create shader program to render the background quad
    bg_shader_program = create_bg_shader_program()

    # Setup fullscreen quad vertices (positions + texture coords)
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

    # Vertex attribute 0 -> position (vec2)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * quad_vertices.itemsize, ctypes.c_void_p(0))

    # Vertex attribute 1 -> texture coordinates (vec2)
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * quad_vertices.itemsize, ctypes.c_void_p(2 * quad_vertices.itemsize))

    glBindBuffer(GL_ARRAY_BUFFER, 0)
    glBindVertexArray(0)

    # Load 3D model objects and shader program for them
    shader_program = create_shader_program()
    glUseProgram(shader_program)
    objects = load_model_from_txt("materials", load_texture)

    # Setup projection and initial camera view matrices
    projection = glm.perspective(glm.radians(config.FOV), display[0] / display[1], config.NEAR_PLANE, config.FAR_PLANE)
    view = glm.lookAt(config.CAMERA_POS, config.CAMERA_TARGET, config.CAMERA_UP)

    # Get uniform locations for matrices and lighting in shader
    proj_loc = glGetUniformLocation(shader_program, "projection")
    view_loc = glGetUniformLocation(shader_program, "view")
    model_loc = glGetUniformLocation(shader_program, "model")
    emissive_loc = glGetUniformLocation(shader_program, "emissiveGlow")
    emissive_col_loc = glGetUniformLocation(shader_program, "emissiveColor")

    # Set projection and view matrices once initially
    glUniformMatrix4fv(proj_loc, 1, GL_FALSE, glm.value_ptr(projection))
    glUniformMatrix4fv(view_loc, 1, GL_FALSE, glm.value_ptr(view))

    # Camera control variables
    camera_distance = 35.00
    rot_x, rot_y = 78.00, 115.00
    rot_2 = 107
    last_mouse_pos = (0, 0)
    mouse_down = False

    clock = pygame.time.Clock()
    running = True
    
    # === AUDIO SETUP ===
    pygame.mixer.music.load("source/audio.mp3")  # Background music
    pygame.mixer.music.play(-1)                   # Loop indefinitely
    pygame.mixer.music.set_volume(0.4)            # Volume between 0.0 and 1.0

    effect_channel = pygame.mixer.Channel(1)      # Separate channel for sound effects

    # Variables for fading background music volume when effects play
    fading = False
    fade_start_time = 0
    fade_back_start_time = 0
    fade_in_progress = None  # Possible states: "out", "waiting", "in", None
    fade_duration = 500      # Fade in/out duration in milliseconds
    fade_back_delay = 2000   # Delay before fading back up in milliseconds

    def fade_volume(start_vol, end_vol, duration, elapsed):
        """Linearly interpolate volume from start_vol to end_vol over duration."""
        if elapsed >= duration:
            return end_vol
        progress = elapsed / duration
        return start_vol + (end_vol - start_vol) * progress

    def trigger(name, sound_file):
        """
        Trigger playing a sound effect while fading background music volume.
        - Starts fading the background music down.
        - Plays the effect sound on a separate channel.
        - Keeps track of glow state timer for objects.
        """
        nonlocal fading, fade_start_time, fade_back_start_time, fade_in_progress
        fading = True
        fade_start_time = pygame.time.get_ticks()
        fade_in_progress = "out"
        fade_back_start_time = 0

        sound = pygame.mixer.Sound(f"source/{sound_file}")
        effect_channel.play(sound)

        glow_states[name] = pygame.time.get_ticks() + 1500  # Glow lasts 1.5 seconds

    # Dictionary tracking glow end times for certain objects
    glow_states = {
        "Charmander": 0,
        "Bulbasaur": 0,
        "Squirtle": 0,
    }

    # Sets of object names for glow grouping
    charizard_parts = {"Charmander", "Fire"}
    bulbasaur_parts = {"Bulbasaur"}
    squirtle_parts = {"Squirtle"}

    while running:
        dt = clock.tick(60)  # Limit to 60 FPS
        now = pygame.time.get_ticks()

        # === EVENT HANDLING ===
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # Print camera info to console and file when 'P' pressed
                if event.key == pygame.K_p:
                    view_info = f"Zoom: {camera_distance:.2f}, rot_x: {rot_x:.2f}, rot_y: {rot_y:.2f}"
                    print(view_info)
                    with open("view_log.txt", "a") as log:
                        log.write(view_info + "\n")

                # Play Charmander sound effect and glow on pressing '1'
                elif event.key == pygame.K_1:
                    trigger("Charmander", "charmander.mp3")

                # Play Bulbasaur sound effect and glow on pressing '2'
                elif event.key == pygame.K_2:
                    trigger("Bulbasaur", "bulba.mp3")

                # Play Squirtle sound effect and glow on pressing '3'
                elif event.key == pygame.K_3:
                    trigger("Squirtle", "squirtle.mp3")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Zoom in on mouse wheel scroll up
                if event.button == 4:
                    camera_distance = max(1.0, camera_distance - 0.5)
                # Zoom out on mouse wheel scroll down
                elif event.button == 5:
                    camera_distance += 0.5
                # Start mouse drag to rotate on left mouse button down
                if event.button == 1:
                    mouse_down = True
                    last_mouse_pos = pygame.mouse.get_pos()

            elif event.type == pygame.MOUSEBUTTONUP:
                # End mouse drag on left mouse button up
                if event.button == 1:
                    mouse_down = False

            elif event.type == pygame.MOUSEMOTION and mouse_down:
                # Rotate camera view based on mouse movement when dragging
                x, y = pygame.mouse.get_pos()
                dx = x - last_mouse_pos[0]
                dy = y - last_mouse_pos[1]
                rot_y += dx * 0.5
                rot_x += dy * 0.5
                last_mouse_pos = (x, y)

        # === HANDLE MUSIC VOLUME FADING ===
        if fading:
            elapsed = now - fade_start_time
            if fade_in_progress == "out":
                # Fade volume down from 0.4 to 0.1
                new_vol = fade_volume(0.4, 0.1, fade_duration, elapsed)
                pygame.mixer.music.set_volume(new_vol)
                if elapsed >= fade_duration:
                    fade_back_start_time = now
                    fade_in_progress = "waiting"
            elif fade_in_progress == "waiting":
                # Wait before fading volume back up
                if now - fade_back_start_time >= fade_back_delay:
                    fade_start_time = now
                    fade_in_progress = "in"
            elif fade_in_progress == "in":
                # Fade volume back up from 0.1 to 0.4
                elapsed_in = now - fade_start_time
                new_vol = fade_volume(0.1, 0.4, fade_duration, elapsed_in)
                pygame.mixer.music.set_volume(new_vol)
                if elapsed_in >= fade_duration:
                    pygame.mixer.music.set_volume(0.4)
                    fading = False
                    fade_in_progress = None

        # === RENDER BACKGROUND ===
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

        # === RENDER 3D SCENE ===
        glEnable(GL_DEPTH_TEST)
        glClear(GL_DEPTH_BUFFER_BIT)

        # Update camera view matrix based on current position and rotation
        view = glm.lookAt(glm.vec3(0, camera_distance, 0), config.CAMERA_TARGET, config.CAMERA_UP)
        glUseProgram(shader_program)
        glUniformMatrix4fv(view_loc, 1, GL_FALSE, glm.value_ptr(view))

        time_sec = now / 1000.0

        # Draw each object with rotation and glow logic
        for obj in objects:
            model_matrix = glm.mat4(1.0)

            # Rotate "spw_gradient" differently from other objects
            if obj.name == "spw_gradient":
                rot_2 += 0.1
                model_matrix = glm.rotate(model_matrix, glm.radians(90), glm.vec3(1, 0, 0))
                model_matrix = glm.rotate(model_matrix, glm.radians(rot_2), glm.vec3(0, 1, 0))
            else:
                model_matrix = glm.rotate(model_matrix, glm.radians(rot_x), glm.vec3(1, 0, 0))
                model_matrix = glm.rotate(model_matrix, glm.radians(rot_y), glm.vec3(0, 1, 0))

            # Apply a bounce effect to most objects except some excluded ones
            exclude_names = ["Grass", "Stage", "Rock", "Grass.001", "Grass.002", "Grass.003",
                             "Grass.004", "Grass.005", "Grass.006"]
            if not any(name in obj.name for name in exclude_names):
                bounce = 0.03 * glm.sin(time_sec * 4.0)
                model_matrix = glm.translate(model_matrix, glm.vec3(0, bounce, 0))

            # Specific bounce for spw_gradient
            if obj.name == "spw_gradient":
                bounce = 0.1 * glm.sin(time_sec * 3.0)
                model_matrix = glm.translate(model_matrix, glm.vec3(0, bounce, 0))

            glUniformMatrix4fv(model_loc, 1, GL_FALSE, glm.value_ptr(model_matrix))

            emissive = False
            glow_color = glm.vec3(0)

            # Set glow color based on object name
            if obj.name == "Charmander":
                emissive = True
                glow_color = glm.vec3(1.0, 0.0, 0.0) * 0.1
            elif obj.name == "Bulbasaur":
                emissive = True
                glow_color = glm.vec3(0.0, 1.0, 0.0) * 0.1
            elif obj.name == "Squirtle":
                emissive = True
                glow_color = glm.vec3(0.0, 0.4, 1.0) * 0.1
            elif obj.name == "Fire":
                emissive = True
                glow_color = glm.vec3(1.0, 0.0, 0.0)

            # Increase glow intensity when active
            if obj.name in charizard_parts and now < glow_states["Charmander"]:
                emissive = True
                glow_color = glm.vec3(1.0, 0.0, 0.0) * 0.3
            elif obj.name in bulbasaur_parts and now < glow_states["Bulbasaur"]:
                emissive = True
                glow_color = glm.vec3(0.0, 1.0, 0.0) * 0.2
            elif obj.name in squirtle_parts and now < glow_states["Squirtle"]:
                emissive = True
                glow_color = glm.vec3(0.0, 0.4, 1.0) * 0.3

            glUniform1i(emissive_loc, int(emissive))
            glUniform3fv(emissive_col_loc, 1, glm.value_ptr(glow_color))

            obj.draw(shader_program, config.TEXTURE_UNITS)

        pygame.display.flip()

    # Cleanup OpenGL resources on exit
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
