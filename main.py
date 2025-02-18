import paramiko
import configparser
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Configurações de conexão SSH
config = configparser.ConfigParser()
config.read("config_file.ini")

SSH_HOST = config.get("SSH", "host", fallback=None)
SSH_PORT = config.getint("SSH", "port", fallback=22)
SSH_USER = config.get("SSH", "user", fallback=None)
SSH_PASSWORD = config.get("SSH", "password", fallback=None)
SSH_KEY_FILE = config.get("SSH", "key_file", fallback=None)

def run_local_command(command):
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    return result.stdout.splitlines(), result.stderr.splitlines()

def run_ssh_command(command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if SSH_KEY_FILE:
            ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY_FILE)
        else:
            ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD)

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().splitlines()
        errors = stderr.read().decode().splitlines()
        ssh.close()
        return output, errors
    except Exception as e:
        return [f"Erro: {str(e)}"], []

def run_command(command):
    stdout, stderr = run_local_command(command) if run_mode.get() == "local" else run_ssh_command(command)
    if stderr:
        update_error_log("\n".join(stderr))
    return stdout

def parse_docker_output(output):
    if not output:
        return [], []
    
    # Define the expected headers
    expected_headers = ['CONTAINER ID', 'IMAGE', 'COMMAND', 'CREATED', 'STATUS', 'PORTS', 'NAMES']
    
    # Check if the first line matches the expected headers
    headers = output[0].split()
    if len(headers) != len(expected_headers):
        # If headers don't match exactly, we'll filter or adjust
        headers = []
        for h in expected_headers:
            if h in output[0]:
                headers.append(h)
        if not headers:
            headers = expected_headers  # Fallback if no match found

    data = []
    for line in output[1:]:
        # Split the line into parts, ensuring we get the right number of fields
        parts = line.split(maxsplit=len(headers) - 1)
        # Ensure each row matches the headers
        row = []
        header_index = 0
        for part in parts:
            if header_index < len(headers):
                row.append(part)
                header_index += 1
        # Append empty strings for any missing columns
        while len(row) < len(headers):
            row.append('')
        data.append(row)

    return headers, data

def update_table(tree, headers, data):
    tree.delete(*tree.get_children())  

    tree["columns"] = headers
    tree["show"] = "headings"

    for col in headers:
        tree.heading(col, text=col)
        tree.column(col, width=120)

    for row in data:
        tree.insert("", "end", values=row)

def refresh_data():
    headers_ps, data_ps = parse_docker_output(run_command("docker ps -a"))
    headers_images, data_images = parse_docker_output(run_command("docker images"))

    update_table(tree_containers, headers_ps, data_ps)
    update_table(tree_images, headers_images, data_images)

def update_error_log(error_message):
    error_text.insert(tk.END, error_message + "\n")
    error_text.see(tk.END)  # Scroll to the bottom

def toggle_dark_mode():
    if dark_mode.get():
        root.configure(bg='#333')
        frame_options.configure(bg='#333', fg='white')
        frame_containers.configure(bg='#333', fg='white')
        frame_images.configure(bg='#333', fg='white')
        error_frame.configure(bg='#333', fg='white')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#555", foreground="white", fieldbackground="#555")
        style.configure("Treeview.Heading", background="#555", foreground="white")
        style.map('TButton', background=[('active', '#444')], foreground=[('active', 'white')])
    else:
        root.configure(bg='SystemButtonFace')
        frame_options.configure(bg='SystemButtonFace', fg='SystemWindowText')
        frame_containers.configure(bg='SystemButtonFace', fg='SystemWindowText')
        frame_images.configure(bg='SystemButtonFace', fg='SystemWindowText')
        error_frame.configure(bg='SystemButtonFace', fg='SystemWindowText')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
        style.configure("Treeview.Heading", background="lightblue", foreground="black")
        style.map('TButton')

def build_image():
    def submit():
        nonlocal dockerfile_path, image_name
        path = dockerfile_path.get()
        name = image_name.get()
        
        if path and name:
            print(path)
            # Convertendo o nome da imagem para minúsculas
            image_name_lower = name.lower()
            command = f"docker build -t {image_name_lower} {path}"
            output = run_command(command)
            messagebox.showinfo("Resultado", "Comando Executado!")
            refresh_data()
            form.destroy()
    
    form = tk.Toplevel(root)
    form.title("Buildar Imagem")
    form.geometry("500x200")
    form.attributes('-topmost', True)
    if dark_mode.get():
        form.configure(bg='#333')
    
    dockerfile_path = tk.StringVar()
    tk.Button(form, text="Selecionar Diretório do Dockerfile", command=lambda: dockerfile_path.set(filedialog.askdirectory()), bg='#444' if dark_mode.get() else 'SystemButtonFace', fg='white' if dark_mode.get() else 'SystemWindowText').pack(pady=5)
    
    image_name = tk.StringVar()
    ttk.Entry(form, textvariable=image_name).pack(pady=5)
    
    ttk.Button(form, text="Buildar", command=submit).pack(pady=5)

def create_container():
    def submit():
        nonlocal image_name, container_name, command, volumes, env_vars, depends_on, networks
        if image_name.get() and container_name.get():
            ports_text = text_area.get("1.0", tk.END).strip()
            volumes_text = volumes_text_area.get("1.0", tk.END).strip()
            env_vars_text = env_text.get("1.0", tk.END).strip()
            depends_on_text = depends_text.get("1.0", tk.END).strip()
            networks_text = networks_text_area.get("1.0", tk.END).strip()

            ports_args = " ".join([f"-p {p.strip()}" for p in ports_text.split(",")]) if ports_text else ""
            volume_args = " ".join([f"-v {v.strip()}" for v in volumes_text.split(",")]) if volumes_text else ""
            env_args = " ".join([f"-e {e.strip()}" for e in env_vars_text.split(",")]) if env_vars_text else ""
            depends_args = " ".join([f"--link {d.strip()}" for d in depends_on_text.split(",")]) if depends_on_text else ""
            network_args = " ".join([f"--network {n.strip()}" for n in networks_text.split(",")]) if networks_text else ""
            
            image = image_name.get().replace("'", "")
            final_command = f"docker run -d --name {container_name.get()}{' ' if ports_args else ''}{ports_args}{' ' if volume_args else ''}{volume_args}{' ' if env_args else ''}{env_args}{' ' if depends_args else ''}{depends_args}{' ' if network_args else ''}{network_args} {image} {command.get()}".strip()
            print(final_command)
            output = run_command(final_command)
            messagebox.showinfo("Resultado", "\n".join(output))
            refresh_data()
            form.destroy()

    form = tk.Toplevel(root)
    form.title("Criar Container")
    form.geometry("800x800")
    form.attributes('-topmost', True)
    if dark_mode.get():
        form.configure(bg='#333')

    canvas = tk.Canvas(form, borderwidth=0, background="#ffffff")
    frame = tk.Frame(canvas, background="#ffffff")
    vsb = tk.Scrollbar(form, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)

    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.create_window((4,4), window=frame, anchor="nw", tags="frame")

    frame.bind("<Configure>", lambda event, canvas=canvas: canvas.configure(scrollregion=canvas.bbox("all")))

    images = run_command("docker images --format '{{.Repository}}'")
    ttk.Label(frame, text='Nome da Imagem').pack(pady=5)
    image_name = tk.StringVar(value=images[0] if images else "")
    ttk.Combobox(frame, textvariable=image_name, values=images).pack(pady=5)

    container_name = tk.StringVar()
    ttk.Label(frame, text='Nome do Container').pack(pady=5)
    ttk.Entry(frame, textvariable=container_name).pack(pady=5)

    command = tk.StringVar(value="")
    ttk.Label(frame, text='Command').pack(pady=5)
    ttk.Entry(frame, textvariable=command).pack(pady=5)

    ports = tk.StringVar()
    ttk.Label(frame, text='Portas').pack(pady=5)
    text_area = tk.Text(frame, width=40, height=5)
    text_area.pack(pady=5)
    text_area.bind("<KeyRelease>", lambda e: ports.set(text_area.get("1.0", tk.END).strip()))

    volumes = tk.StringVar()
    ttk.Label(frame, text='Volumes').pack(pady=5)
    volumes_text_area = tk.Text(frame, width=40, height=5)
    volumes_text_area.pack(pady=5)
    volumes_text_area.bind("<KeyRelease>", lambda e: volumes.set(volumes_text_area.get("1.0", tk.END).strip()))

    env_vars = tk.StringVar()
    ttk.Label(frame, text='Variáveis de Ambiente').pack(pady=5)
    env_text = tk.Text(frame, width=40, height=5)
    env_text.pack(pady=5)
    env_text.bind("<KeyRelease>", lambda e: env_vars.set(env_text.get("1.0", tk.END).strip()))

    depends_on = tk.StringVar()
    ttk.Label(frame, text='Depende de').pack(pady=5)
    depends_text = tk.Text(frame, width=40, height=5)
    depends_text.pack(pady=5)
    depends_text.bind("<KeyRelease>", lambda e: depends_on.set(depends_text.get("1.0", tk.END).strip()))

    networks = tk.StringVar()
    ttk.Label(frame, text='Redes').pack(pady=5)
    networks_text_area = tk.Text(frame, width=40, height=5)
    networks_text_area.pack(pady=5)
    networks_text_area.bind("<KeyRelease>", lambda e: networks.set(networks_text_area.get("1.0", tk.END).strip()))

    ttk.Button(frame, text="Submit", command=submit).pack(pady=5)

    canvas.bind("<Configure>", lambda e: canvas.itemconfig("frame", width=e.width))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

def delete_image():
    def submit():
        nonlocal image_name
        selected_image = image_name.get()
        if selected_image:
            clean_image_name = selected_image.replace("'", "")
            command = f"docker rmi {clean_image_name}"
            output, errors = run_command(command)
            messagebox.showinfo("Resultado", "Comando Executado!")
            refresh_data()
            form.destroy()

    form = tk.Toplevel(root)
    form.title("Deletar Imagem")
    form.geometry("500x200")
    form.attributes('-topmost', True)
    if dark_mode.get():
        form.configure(bg='#333')

    images = run_command("docker images --format '{{.Repository}}:{{.Tag}}'")
    image_name = tk.StringVar(value=images[0] if images else "")
    ttk.Combobox(form, textvariable=image_name, values=images, width=40).pack(pady=5)
    
    ttk.Button(form, text="Deletar", command=submit).pack(pady=5)

def stop_or_remove_container():
    def submit():
        nonlocal container_name, action
        selected_container = container_name.get()
        selected_action = action.get()
        if selected_container and selected_action in ["stop", "rm"]:
            clean_container_name = selected_container.replace("'", "")
            print(f"docker {selected_action} {clean_container_name}")
            output = run_command(f"docker {selected_action} {clean_container_name}")
            messagebox.showinfo("Resultado", "\n".join(output))
            refresh_data()
            form.destroy()

    form = tk.Toplevel(root)
    form.title("Parar/Remover Container")
    form.geometry("500x200")
    form.attributes('-topmost', True)
    if dark_mode.get():
        form.configure(bg='#333')

    containers = run_command("docker ps -a --format '{{.Names}}'")
    container_name = tk.StringVar(value=containers[0] if containers else "")
    ttk.Combobox(form, textvariable=container_name, values=containers).pack(pady=5)

    action = tk.StringVar()
    ttk.Combobox(form, textvariable=action, values=["stop", "rm"]).pack(pady=5)

    ttk.Button(form, text="Submit", command=submit).pack(pady=5)

def create_scrollable_frame(master, text):
    frame = ttk.LabelFrame(master, text=text)
    canvas = tk.Canvas(frame)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    return frame, scrollable_frame

# Interface gráfica
root = tk.Tk()
root.title("Gerenciador Docker")

run_mode = tk.StringVar(value="local")
dark_mode = tk.BooleanVar(value=False)

style = ttk.Style()
style.theme_use('clam')

frame_options = ttk.LabelFrame(root, text="Modo de Execução")
frame_options.pack(fill="both", expand=True, padx=10, pady=5)
ttk.Radiobutton(frame_options, text="Rodar Localmente", variable=run_mode, value="local").pack(anchor="w", padx=5, pady=2)
ttk.Radiobutton(frame_options, text="Rodar via SSH", variable=run_mode, value="ssh").pack(anchor="w", padx=5, pady=2)

frame_containers, scrollable_containers = create_scrollable_frame(root, "Containers")
frame_containers.pack(fill="both", expand=True, padx=10, pady=5)

frame_images, scrollable_images = create_scrollable_frame(root, "Imagens")
frame_images.pack(fill="both", expand=True, padx=10, pady=5)

tree_containers = ttk.Treeview(scrollable_containers)
tree_containers.pack(fill="both", expand=True)

tree_images = ttk.Treeview(scrollable_images)
tree_images.pack(fill="both", expand=True)

error_frame, scrollable_error = create_scrollable_frame(root, "Terminal da Aplicação")
error_frame.pack(fill="both", expand=True, padx=10, pady=5)

error_text = tk.Text(scrollable_error, wrap=tk.WORD, width=80, height=10, bg='#555' if dark_mode.get() else 'white', fg='white' if dark_mode.get() else 'black')
error_text.pack(fill=tk.BOTH, expand=True)

# Toggle para modo dark
ttk.Checkbutton(root, text="Modo Escuro", variable=dark_mode, command=toggle_dark_mode).pack(pady=5)

ttk.Button(root, text="Atualizar", command=refresh_data).pack(pady=5)
ttk.Button(root, text="Buildar Imagem", command=build_image).pack(pady=5)
ttk.Button(root, text="Criar Container", command=create_container).pack(pady=5)
ttk.Button(root, text="Parar/Remover Container", command=stop_or_remove_container).pack(pady=5)
ttk.Button(root, text="Deletar Imagem", command=delete_image).pack(pady=5)

refresh_data()
root.mainloop()