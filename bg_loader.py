from OpenGL.GL import *

bg_vertex_shader = """
#version 330 core
layout(location = 0) in vec2 position;
layout(location = 1) in vec2 texCoord;

out vec2 TexCoord;

void main()
{
    gl_Position = vec4(position, 0.0, 1.0);
    TexCoord = texCoord;
}
"""

bg_fragment_shader = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform sampler2D backgroundTexture;

void main()
{
    FragColor = texture(backgroundTexture, TexCoord);
}
"""

def create_bg_shader_program():
    vs = glCreateShader(GL_VERTEX_SHADER)
    fs = glCreateShader(GL_FRAGMENT_SHADER)
    glShaderSource(vs, bg_vertex_shader)
    glShaderSource(fs, bg_fragment_shader)
    glCompileShader(vs)
    glCompileShader(fs)

    # Check compilation
    for shader, name in [(vs, "BG VERTEX"), (fs, "BG FRAGMENT")]:
        success = glGetShaderiv(shader, GL_COMPILE_STATUS)
        if not success:
            info_log = glGetShaderInfoLog(shader)
            print(f"ERROR::SHADER_COMPILATION_ERROR of type: {name}\n{info_log.decode()}")

    program = glCreateProgram()
    glAttachShader(program, vs)
    glAttachShader(program, fs)
    glLinkProgram(program)

    # Check linking
    success = glGetProgramiv(program, GL_LINK_STATUS)
    if not success:
        info_log = glGetProgramInfoLog(program)
        print(f"ERROR::PROGRAM_LINKING_ERROR\n{info_log.decode()}")

    glDeleteShader(vs)
    glDeleteShader(fs)

    return program