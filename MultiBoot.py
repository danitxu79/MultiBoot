#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import json
import threading
import shutil
import time

# Punto de montaje temporal para el USB
TEMP_MOUNT_POINT = "/mnt/multiboot_usb_creator_temp"


class MultibootUSBApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Creador y Gestor USB Multiboot para Linux")
        self.root.geometry("750x750")  # Ajustar tamaño para nueva sección

        self.iso_files = []  # Para la creación inicial
        self.current_usb_device_path = None  # Para gestión
        self.current_usb_partition1 = None  # Para gestión

        # --- Log Area (Común) ---
        # Mover la inicialización del log_area aquí, ANTES de que se use.
        log_frame_outer = ttk.Frame(
            self.root
        )  # Usar un frame para controlar el empaquetado después
        log_frame_inner = ttk.LabelFrame(log_frame_outer, text="Log de Operaciones")
        self.log_area = scrolledtext.ScrolledText(
            log_frame_inner, wrap=tk.WORD, height=8, state=tk.DISABLED
        )
        self.log_area.pack(padx=5, pady=5, fill="both", expand=True)
        log_frame_inner.pack(padx=10, pady=10, fill="both", expand=True)
        # El log_frame_outer se empaquetará al final de __init__

        # --- Check de Root y Dependencias ---
        if os.geteuid() != 0:
            messagebox.showerror(
                "Error de Permisos", "Este script debe ejecutarse como root (con sudo)."
            )
            self.root.destroy()
            return
        if (
            not self.check_dependencies()
        ):  # Ahora log_message puede ser llamado desde aquí
            self.root.destroy()
            return

        # --- Sección de Selección de USB (Común para Crear y Gestionar) ---
        top_usb_frame = ttk.LabelFrame(self.root, text="Dispositivo USB")
        top_usb_frame.pack(padx=10, pady=10, fill="x")  # Empaquetar este frame aquí

        ttk.Label(top_usb_frame, text="Dispositivo USB:").pack(
            side=tk.LEFT, padx=5, pady=5
        )
        self.usb_var = tk.StringVar()
        self.usb_combo = ttk.Combobox(
            top_usb_frame, textvariable=self.usb_var, state="readonly", width=45
        )
        self.usb_combo.pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill="x")
        self.usb_combo.bind("<<ComboboxSelected>>", self.on_usb_selected)

        refresh_button = ttk.Button(
            top_usb_frame,
            text="Refrescar Lista USBs",
            command=self.populate_usb_devices,
        )
        refresh_button.pack(side=tk.LEFT, padx=5, pady=5)

        # --- Notebook para Crear vs Gestionar ---
        self.notebook = ttk.Notebook(self.root)
        # El notebook se empaquetará DESPUÉS del log_frame_outer para que el log quede abajo

        # --- Pestaña: Crear Nuevo USB Multiboot ---
        create_tab = ttk.Frame(self.notebook)
        self.notebook.add(create_tab, text="Crear Nuevo USB Multiboot")
        self._populate_create_tab(create_tab)

        # --- Pestaña: Gestionar USB Existente ---
        manage_tab = ttk.Frame(self.notebook)
        self.notebook.add(manage_tab, text="Gestionar USB Existente")
        self._populate_manage_tab(manage_tab)

        # Empaquetar el notebook y luego el log_frame_outer
        self.notebook.pack(padx=10, pady=10, fill="both", expand=True)
        log_frame_outer.pack(
            padx=0, pady=0, fill="both", expand=True
        )  # El padx/pady ya está en log_frame_inner

        self.populate_usb_devices()  # Ahora log_message puede ser llamado desde aquí
        self._update_manage_ui_state(
            is_compatible=False
        )  # Inicialmente deshabilitar gestión

    # ... (el resto de los métodos _populate_create_tab, _populate_manage_tab, etc., permanecen igual)
    # ... (asegúrate de que todas las funciones que has pegado anteriormente estén aquí)

    def _populate_create_tab(self, parent_tab):
        # --- Sección de Selección de ISOs (para Crear) ---
        iso_frame = ttk.LabelFrame(
            parent_tab, text="1. Seleccionar Archivos ISO para Nuevo USB"
        )
        iso_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.iso_listbox_create = tk.Listbox(
            iso_frame, selectmode=tk.SINGLE, width=60, height=5
        )
        self.iso_listbox_create.pack(
            padx=5, pady=5, side=tk.LEFT, fill="both", expand=True
        )

        iso_button_frame = ttk.Frame(iso_frame)
        iso_button_frame.pack(side=tk.LEFT, padx=5, pady=5, fill="y")
        add_iso_button = ttk.Button(
            iso_button_frame, text="Añadir ISO", command=self.add_iso_for_create
        )
        add_iso_button.pack(pady=5, fill="x")
        remove_iso_button = ttk.Button(
            iso_button_frame, text="Quitar ISO", command=self.remove_iso_for_create
        )
        remove_iso_button.pack(pady=5, fill="x")

        # --- Sección de Creación y Progreso (para Crear) ---
        action_frame_create = ttk.LabelFrame(
            parent_tab, text="2. Crear USB y Ver Progreso"
        )
        action_frame_create.pack(padx=10, pady=10, fill="both", expand=True)

        self.create_button = ttk.Button(
            action_frame_create,
            text="¡Crear USB Multiboot!",
            command=self.start_creation_process,
        )
        self.create_button.pack(pady=10)

        self.progress_info_frame_create = ttk.Frame(action_frame_create)
        self.progress_info_frame_create.pack(fill="x", padx=5, pady=(0, 5))
        self.current_iso_label_var_create = tk.StringVar(value="Progreso de copia: N/A")
        current_iso_widget_create = ttk.Label(
            self.progress_info_frame_create,
            textvariable=self.current_iso_label_var_create,
            anchor="w",
        )
        current_iso_widget_create.pack(fill="x")
        self.progress_bar_create = ttk.Progressbar(
            self.progress_info_frame_create,
            orient="horizontal",
            length=300,
            mode="determinate",
        )
        self.progress_bar_create.pack(fill="x", pady=(0, 5))

    def _populate_manage_tab(self, parent_tab):
        manage_info_label = ttk.Label(
            parent_tab,
            text="Selecciona un dispositivo USB de la lista superior. Si es compatible, se listarán sus ISOs.",
            wraplength=600,
        )
        manage_info_label.pack(padx=10, pady=10)

        # --- Listado de ISOs en el USB Montado ---
        mounted_iso_frame = ttk.LabelFrame(
            parent_tab, text="ISOs en el USB Seleccionado"
        )
        mounted_iso_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.mounted_iso_listbox = tk.Listbox(
            mounted_iso_frame, selectmode=tk.SINGLE, width=60, height=6
        )
        self.mounted_iso_listbox.pack(
            padx=5, pady=5, side=tk.LEFT, fill="both", expand=True
        )

        mounted_iso_buttons = ttk.Frame(mounted_iso_frame)
        mounted_iso_buttons.pack(side=tk.LEFT, padx=5, pady=5, fill="y")
        self.refresh_mounted_isos_button = ttk.Button(
            mounted_iso_buttons,
            text="Refrescar Lista del USB",
            command=self.refresh_isos_on_selected_usb,
        )
        self.refresh_mounted_isos_button.pack(pady=5, fill="x")

        # --- Acciones de Gestión ---
        manage_actions_frame = ttk.LabelFrame(parent_tab, text="Acciones de Gestión")
        manage_actions_frame.pack(padx=10, pady=10, fill="x")

        self.add_to_usb_button = ttk.Button(
            manage_actions_frame,
            text="Añadir Nuevo ISO al USB",
            command=self.start_add_iso_to_usb_process,
        )
        self.add_to_usb_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.remove_from_usb_button = ttk.Button(
            manage_actions_frame,
            text="Quitar ISO Seleccionado del USB",
            command=self.start_remove_iso_from_usb_process,
        )
        self.remove_from_usb_button.pack(side=tk.LEFT, padx=10, pady=10)

        # Progreso para la pestaña de gestión (principalmente para añadir ISO)
        self.progress_info_frame_manage = ttk.Frame(parent_tab)
        self.progress_info_frame_manage.pack(fill="x", padx=10, pady=(5, 10))
        self.current_iso_label_var_manage = tk.StringVar(value="Progreso de copia: N/A")
        current_iso_widget_manage = ttk.Label(
            self.progress_info_frame_manage,
            textvariable=self.current_iso_label_var_manage,
            anchor="w",
        )
        current_iso_widget_manage.pack(fill="x")
        self.progress_bar_manage = ttk.Progressbar(
            self.progress_info_frame_manage,
            orient="horizontal",
            length=300,
            mode="determinate",
        )
        self.progress_bar_manage.pack(fill="x", pady=(0, 5))

    def log_message(self, message):
        if hasattr(self, "log_area") and self.log_area:  # Comprobar si log_area existe
            self.log_area.configure(state=tk.NORMAL)
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.configure(state=tk.DISABLED)
            self.log_area.see(tk.END)
            if (
                hasattr(self, "root") and self.root.winfo_exists()
            ):  # Comprobar si root existe
                self.root.update_idletasks()
        else:
            print(
                f"LOG (pre-GUI): {message}"
            )  # Fallback a consola si log_area no está lista

    def run_command(self, command_list, check=True, capture_output=False, log_cmd=True):
        if log_cmd:
            self.log_message(f"Ejecutando: {' '.join(command_list)}")
        try:
            process = subprocess.run(
                command_list,
                check=check,
                text=True,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE,
            )
            if capture_output and process.stdout and log_cmd:
                self.log_message(f"Salida: {process.stdout.strip()}")
            if (
                process.stderr and log_cmd
            ):  # Mostrar stderr incluso si el comando tiene éxito, como advertencias
                self.log_message(f"Stderr: {process.stderr.strip()}")

            if (
                check and process.returncode != 0
            ):  # Si check=True pero el CalledProcessError no fue lanzado (a veces pasa con capture_output manual)
                raise subprocess.CalledProcessError(
                    process.returncode,
                    command_list,
                    output=process.stdout,
                    stderr=process.stderr,
                )

            return process.stdout.strip() if capture_output else True
        except subprocess.CalledProcessError as e:
            if log_cmd:
                self.log_message(f"Error ejecutando comando: {e}")
                if e.stdout:
                    self.log_message(f"Salida (stdout) del error: {e.stdout.strip()}")
                if e.stderr:
                    self.log_message(f"Salida (stderr) del error: {e.stderr.strip()}")
            return False
        except FileNotFoundError:
            if log_cmd:
                self.log_message(f"Error: Comando '{command_list[0]}' no encontrado.")
            return False

    def check_dependencies(self):
        dependencies = [
            "lsblk",
            "parted",
            "mkfs.fat",
            "grub-install",
            "dd",
            "umount",
            "mount",
            "partprobe",
        ]
        missing = []
        for dep in dependencies:
            if shutil.which(dep) is None:
                missing.append(dep)

        if missing:
            # No usar self.log_message aquí directamente si puede fallar, messagebox es más seguro en esta etapa temprana
            messagebox.showerror(
                "Dependencias Faltantes",
                f"Las siguientes dependencias no se encontraron: {', '.join(missing)}.\n"
                "Por favor, instálalas e inténtalo de nuevo.",
            )
            return False
        self.log_message(
            "Todas las dependencias necesarias están presentes."
        )  # Ahora esto debería funcionar
        return True

    def populate_usb_devices(self):
        self.log_message("Buscando dispositivos USB...")
        self.usb_combo.set("")
        self.usb_var.set("")

        try:
            result = subprocess.run(
                ["lsblk", "-dJ", "-o", "NAME,SIZE,MODEL,TRAN,TYPE,PATH"],
                capture_output=True,
                text=True,
                check=True,
            )
            devices_data = json.loads(result.stdout)

            usb_devices = []
            if "blockdevices" in devices_data:
                for device in devices_data["blockdevices"]:
                    if (
                        device.get("tran") == "usb"
                        and device.get("type") == "disk"
                        and device.get("name")
                    ):
                        path = device.get("path", f"/dev/{device['name']}")
                        model = device.get("model", "N/A")
                        size = device.get("size", "N/A")
                        display_name = f"{path} - {model} ({size})"
                        usb_devices.append(display_name)

            self.usb_combo["values"] = usb_devices
            if usb_devices:
                self.usb_combo.current(0)
                self.on_usb_selected()  # Auto-seleccionar y verificar el primero
                self.log_message(
                    f"Encontrados {len(usb_devices)} dispositivos USB. Verificando el primero..."
                )
            else:
                self.log_message(
                    "No se encontraron dispositivos USB. Asegúrate de que estén conectados."
                )
                self._update_manage_ui_state(
                    is_compatible=False
                )  # Deshabilitar gestión si no hay USBs
        except subprocess.CalledProcessError as e:
            self.log_message(
                f"Error al listar dispositivos: {e.stderr if e.stderr else str(e)}"
            )
            messagebox.showerror(
                "Error",
                f"No se pudieron listar los dispositivos USB: {e.stderr if e.stderr else str(e)}",
            )
        except json.JSONDecodeError as e:
            self.log_message(f"Error al parsear salida de lsblk: {e}")
            messagebox.showerror("Error", "Error al procesar la lista de dispositivos.")
        except FileNotFoundError:
            self.log_message("Error: comando 'lsblk' no encontrado.")
            messagebox.showerror(
                "Error",
                "El comando 'lsblk' no está disponible. Asegúrate de que 'util-linux' esté instalado.",
            )

    def add_iso_for_create(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar Archivo ISO",
            filetypes=(("Archivos ISO", "*.iso"), ("Todos los archivos", "*.*")),
        )
        if filepath and filepath not in self.iso_files:
            self.iso_files.append(filepath)
            self.iso_listbox_create.insert(tk.END, os.path.basename(filepath))
            self.log_message(f"ISO añadida para creación: {filepath}")

    def remove_iso_for_create(self):
        selected_indices = self.iso_listbox_create.curselection()
        if not selected_indices:
            return
        index = selected_indices[0]
        iso_to_remove_display = self.iso_listbox_create.get(index)
        path_to_remove = next(
            (p for p in self.iso_files if os.path.basename(p) == iso_to_remove_display),
            None,
        )
        if path_to_remove:
            self.iso_files.remove(path_to_remove)
            self.iso_listbox_create.delete(index)
            self.log_message(f"ISO quitada de la lista de creación: {path_to_remove}")

    def _get_selected_usb_paths(self):
        selected_usb_display = self.usb_var.get()
        if not selected_usb_display:
            return None, None

        device_path = selected_usb_display.split(" - ")[0]
        partition1 = device_path + "1"
        if (
            "mmcblk" in device_path
            and "p" not in os.path.basename(device_path)
            and not device_path.endswith("p")
        ):  # ej. /dev/mmcblk0
            partition1 = device_path + "p1"
        elif (
            "loop" in device_path
            and "p" not in os.path.basename(device_path)
            and not device_path.endswith("p")
        ):  # ej. /dev/loop0
            partition1 = device_path + "p1"
        # Añadir más lógica si es necesario para otros tipos de dispositivos como nvme (e.g., /dev/nvme0n1p1)
        # Por ahora, esto cubre sdX y mmcblkX
        return device_path, partition1

    def on_usb_selected(self, event=None):
        self.current_usb_device_path, self.current_usb_partition1 = (
            self._get_selected_usb_paths()
        )
        if self.current_usb_device_path:
            self.log_message(
                f"USB seleccionado: {self.current_usb_device_path}. Verificando compatibilidad para gestión..."
            )
            self.verify_and_load_isos_from_usb()
        else:
            self._update_manage_ui_state(is_compatible=False)

    def _update_manage_ui_state(self, is_compatible, isos_found=False):
        # Verifica que los widgets existan antes de configurarlos
        # Esto es útil si la función se llama antes de que _populate_manage_tab haya completado
        # o si hay un error muy temprano en __init__
        if not hasattr(
            self, "add_to_usb_button"
        ):  # Asumir que si uno no existe, los otros tampoco
            return

        if is_compatible:
            self.add_to_usb_button.config(state=tk.NORMAL)
            self.refresh_mounted_isos_button.config(state=tk.NORMAL)
            # Habilitar quitar si hay ISOs. No depende de selección para habilitación inicial del botón.
            # La comprobación de selección se hará al pulsar el botón.
            if isos_found:
                self.remove_from_usb_button.config(state=tk.NORMAL)
            else:
                self.remove_from_usb_button.config(state=tk.DISABLED)
        else:
            if hasattr(self, "mounted_iso_listbox"):
                self.mounted_iso_listbox.delete(0, tk.END)
            self.add_to_usb_button.config(state=tk.DISABLED)
            self.remove_from_usb_button.config(state=tk.DISABLED)
            self.refresh_mounted_isos_button.config(state=tk.DISABLED)
            # No resetear current_usb_device_path aquí, on_usb_selected lo maneja.

    def verify_and_load_isos_from_usb(self):
        if not self.current_usb_partition1:
            self._update_manage_ui_state(is_compatible=False)
            self.log_message("No hay partición USB válida para verificar.")
            return False  # Añadido retorno para claridad

        if hasattr(self, "mounted_iso_listbox"):
            self.mounted_iso_listbox.delete(0, tk.END)
        self.log_message(
            f"Intentando verificar {self.current_usb_partition1} en {TEMP_MOUNT_POINT}..."
        )

        self.run_command(["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False)
        if not os.path.exists(TEMP_MOUNT_POINT):
            if not self.run_command(["mkdir", "-p", TEMP_MOUNT_POINT]):
                self.log_message(
                    f"Error: No se pudo crear el punto de montaje {TEMP_MOUNT_POINT}."
                )
                self._update_manage_ui_state(is_compatible=False)
                return False

        is_compatible_usb = False
        isos_on_device = []
        # Usar un bloque try-finally para asegurar el desmontaje
        try:
            if self.run_command(
                ["mount", self.current_usb_partition1, TEMP_MOUNT_POINT]
            ):
                grub_cfg_path = os.path.join(TEMP_MOUNT_POINT, "boot/grub/grub.cfg")
                isos_dir = os.path.join(TEMP_MOUNT_POINT, "isos")
                if os.path.exists(grub_cfg_path) and os.path.isdir(isos_dir):
                    self.log_message(
                        f"USB {self.current_usb_device_path} parece compatible (estructura encontrada)."
                    )
                    is_compatible_usb = True
                    for item in os.listdir(isos_dir):
                        if item.lower().endswith(".iso"):
                            isos_on_device.append(item)
                            if hasattr(self, "mounted_iso_listbox"):
                                self.mounted_iso_listbox.insert(tk.END, item)
                    if isos_on_device:
                        self.log_message(
                            f"ISOs encontrados en {isos_dir}: {', '.join(isos_on_device)}"
                        )
                    else:
                        self.log_message(
                            f"Directorio 'isos' encontrado pero vacío en {self.current_usb_device_path}."
                        )
                else:
                    self.log_message(
                        f"USB {self.current_usb_device_path} no parece compatible (falta grub.cfg o dir /isos)."
                    )
            else:
                self.log_message(
                    f"No se pudo montar {self.current_usb_partition1} para verificación."
                )
        finally:
            if os.path.ismount(
                TEMP_MOUNT_POINT
            ):  # Solo intentar desmontar si está montado
                self.run_command(["umount", TEMP_MOUNT_POINT], check=False)

        self._update_manage_ui_state(is_compatible_usb, isos_found=bool(isos_on_device))
        return is_compatible_usb  # Retornar el estado

    def refresh_isos_on_selected_usb(self):
        if self.current_usb_device_path:
            self.log_message(
                f"Refrescando lista de ISOs para {self.current_usb_device_path}..."
            )
            self.verify_and_load_isos_from_usb()
        else:
            self.log_message("Ningún USB seleccionado para refrescar.")
            messagebox.showinfo(
                "Información", "Por favor, selecciona un dispositivo USB primero."
            )

    def _update_progress(
        self, bar_widget, label_var_widget, value, maximum=None, label_text=None
    ):
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return  # No hacer nada si la GUI no existe

        if bar_widget:  # Comprobar si el widget existe
            if maximum is not None:
                bar_widget.config(maximum=maximum)
            bar_widget.config(value=value)
        if label_var_widget and label_text is not None:  # Comprobar si el widget existe
            label_var_widget.set(label_text)

    def start_creation_process(self):
        device_path, _ = self._get_selected_usb_paths()
        if not device_path:
            messagebox.showerror(
                "Error", "Por favor, selecciona un dispositivo USB para crear."
            )
            return
        if not self.iso_files:
            messagebox.showerror(
                "Error", "Por favor, añade al menos un archivo ISO para la creación."
            )
            return

        confirm_msg = (
            f"¡ADVERTENCIA! Esto formateará COMPLETAMENTE el dispositivo:\n"
            f"{device_path}\n"
            f"TODOS LOS DATOS EN ESTE DISPOSITIVO SE PERDERÁN.\n\n"
            "¿Estás absolutamente seguro de que quieres continuar?"
        )
        if messagebox.askyesno(
            "Confirmar Acción Peligrosa", confirm_msg, icon="warning"
        ):
            self.create_button.config(state=tk.DISABLED)
            self.log_message("Iniciando proceso de creación del USB...")
            self.root.after(
                0,
                self._update_progress,
                self.progress_bar_create,
                self.current_iso_label_var_create,
                0,
                100,
                "Iniciando...",
            )

            thread = threading.Thread(
                target=self.create_multiboot_usb_worker,
                args=(device_path, list(self.iso_files)),
            )
            thread.daemon = True
            thread.start()
        else:
            self.log_message("Proceso de creación cancelado.")

    def create_multiboot_usb_worker(self, device_path, iso_list_paths):
        # Esta función debe estar completa como en la respuesta anterior
        # El traceback no indica un problema aquí, pero asegúrate de que esté completa.
        # La clave es que las llamadas a self.root.after usen self.progress_bar_create y self.current_iso_label_var_create
        try:
            self.log_message(f"Dispositivo para creación: {device_path}")
            device_partition1, _ = (
                self._get_selected_usb_paths()
            )  # Usar el helper para consistencia
            # Si _get_selected_usb_paths devuelve None para la partición si el device_path no es lo esperado
            # Necesitamos recalcularlo basado en device_path específicamente para la creación.

            current_display_device = (
                self.usb_var.get()
            )  # El string completo del combobox
            actual_device_path_from_combo, actual_partition1_from_combo = (
                self._get_selected_usb_paths()
            )

            if device_path != actual_device_path_from_combo:
                self.log_message(
                    f"Advertencia: device_path ({device_path}) no coincide con el combo ({actual_device_path_from_combo}). Usando el del combo."
                )
                device_path = actual_device_path_from_combo  # Asegurar que usamos el device_path del combo

            # Recalcular part1 basado en el device_path definitivo
            device_partition1 = device_path + "1"
            if (
                "mmcblk" in device_path
                and "p" not in os.path.basename(device_path)
                and not device_path.endswith("p")
            ):
                device_partition1 = device_path + "p1"
            elif (
                "loop" in device_path
                and "p" not in os.path.basename(device_path)
                and not device_path.endswith("p")
            ):
                device_partition1 = device_path + "p1"

            self.log_message(
                f"Partición objetivo para formateo/montaje: {device_partition1}"
            )

            # 1. Desmontar
            self.log_message(f"Intentando desmontar particiones en {device_path}...")
            try:
                result = subprocess.run(
                    ["lsblk", "-no", "MOUNTPOINT,NAME", device_path],
                    capture_output=True,
                    text=True,
                )
                if result.stdout:
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split()
                        if len(parts) > 1 and parts[0] and parts[0] != "[SWAP]":
                            mountpoint = parts[0]
                            part_name_suffix = parts[-1].split("/")[-1]
                            if not any(
                                part_name_suffix.startswith(prefix)
                                for prefix in ["sd", "nvme", "hd", "mmcblk", "loop"]
                            ):
                                potential_parent = device_path.split("/")[-1]
                                if part_name_suffix.startswith(potential_parent):
                                    partition_name_to_umount = (
                                        f"/dev/{part_name_suffix}"
                                    )
                                else:
                                    partition_name_to_umount = (
                                        f"/dev/{potential_parent}{part_name_suffix}"
                                    )
                            else:
                                partition_name_to_umount = f"/dev/{part_name_suffix}"

                            self.log_message(
                                f"Desmontando {partition_name_to_umount} de {mountpoint}..."
                            )
                            if not self.run_command(
                                ["umount", partition_name_to_umount]
                            ):
                                self.log_message(
                                    f"Desmontaje normal de {partition_name_to_umount} falló, intentando forzado..."
                                )
                                if not self.run_command(
                                    ["umount", "-lf", partition_name_to_umount]
                                ):
                                    raise Exception(
                                        f"No se pudo desmontar {partition_name_to_umount}"
                                    )
            except Exception as e:
                self.log_message(f"Error durante el desmontaje inicial: {e}")

            # 2. Particionar y formatear
            if not self.run_command(["parted", "-s", device_path, "mklabel", "msdos"]):
                raise Exception("Fallo mklabel")
            if not self.run_command(
                [
                    "parted",
                    "-s",
                    device_path,
                    "mkpart",
                    "primary",
                    "fat32",
                    "1MiB",
                    "100%",
                ]
            ):
                raise Exception("Fallo mkpart")
            if not self.run_command(
                ["parted", "-s", device_path, "set", "1", "boot", "on"]
            ):
                raise Exception("Fallo set boot on")

            self.log_message("Esperando y releyendo tabla de particiones...")
            time.sleep(3)
            self.run_command(["partprobe", device_path], check=False, log_cmd=False)
            time.sleep(3)  # Dar más tiempo

            self.log_message(f"Formateando {device_partition1} como FAT32...")
            if not self.run_command(["mkfs.fat", "-F32", device_partition1]):
                self.log_message(
                    f"Primer intento de mkfs.fat en {device_partition1} falló. Esperando más y reintentando..."
                )
                time.sleep(5)  # Más tiempo para que el kernel actualice
                self.run_command(["partprobe", device_path], check=False, log_cmd=False)
                time.sleep(2)
                if not self.run_command(["mkfs.fat", "-F32", device_partition1]):
                    raise Exception(
                        f"Fallo al formatear {device_partition1} como FAT32 tras reintento"
                    )

            # 3. Montar
            self.run_command(
                ["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False
            )  # Asegurar que no esté montado
            if not os.path.exists(TEMP_MOUNT_POINT):
                self.run_command(["mkdir", "-p", TEMP_MOUNT_POINT])
            if not self.run_command(["mount", device_partition1, TEMP_MOUNT_POINT]):
                raise Exception(
                    f"Fallo al montar {device_partition1} en {TEMP_MOUNT_POINT}"
                )

            # 4. Instalar GRUB
            grub_boot_dir = os.path.join(TEMP_MOUNT_POINT, "boot")
            self.log_message(
                f"Instalando GRUB2 en {device_path} (directorio de arranque: {grub_boot_dir})..."
            )
            if not self.run_command(
                [
                    "grub-install",
                    f"--boot-directory={grub_boot_dir}",
                    "--target=i386-pc",
                    "--no-floppy",
                    device_path,
                ]
            ):
                self.log_message("grub-install falló. Intentando con --force...")
                if not self.run_command(
                    [
                        "grub-install",
                        f"--boot-directory={grub_boot_dir}",
                        "--target=i386-pc",
                        "--no-floppy",
                        "--force",
                        device_path,
                    ]
                ):
                    raise Exception(f"Fallo al instalar GRUB2 en {device_path}")

            # 5. Copiar ISOs
            isos_dir_on_usb = os.path.join(TEMP_MOUNT_POINT, "isos")
            self.run_command(["mkdir", "-p", isos_dir_on_usb])
            iso_filenames_on_usb = []
            total_isos_to_copy = len(iso_list_paths)

            for idx, iso_path in enumerate(iso_list_paths):
                iso_filename = os.path.basename(iso_path)
                dest_iso_path = os.path.join(isos_dir_on_usb, iso_filename)
                current_iso_info = (
                    f"Copiando ({idx + 1}/{total_isos_to_copy}): {iso_filename}"
                )
                # self.log_message(current_iso_info) # Ya se loguea en _update_progress

                file_size = os.path.getsize(iso_path)
                self.root.after(
                    0,
                    self._update_progress,
                    self.progress_bar_create,
                    self.current_iso_label_var_create,
                    0,
                    file_size,
                    current_iso_info,
                )

                copied_bytes = 0
                buffer_size = 1024 * 1024
                try:
                    with (
                        open(iso_path, "rb") as fsrc,
                        open(dest_iso_path, "wb") as fdst,
                    ):
                        while True:
                            chunk = fsrc.read(buffer_size)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            copied_bytes += len(chunk)
                            self.root.after(
                                0,
                                self._update_progress,
                                self.progress_bar_create,
                                self.current_iso_label_var_create,
                                copied_bytes,
                                None,
                                None,
                            )  # Solo valor
                    iso_filenames_on_usb.append(iso_filename)
                    self.root.after(
                        0,
                        self._update_progress,
                        self.progress_bar_create,
                        self.current_iso_label_var_create,
                        file_size,
                        None,
                        None,
                    )  # 100%
                except Exception as e:
                    self.log_message(f"Error copiando {iso_filename}: {e}")
                    self.root.after(
                        0,
                        self._update_progress,
                        self.progress_bar_create,
                        self.current_iso_label_var_create,
                        0,
                        None,
                        f"Error copiando {iso_filename}",
                    )

            if not iso_filenames_on_usb:
                raise Exception("No se pudo copiar ningún ISO al USB.")
            self.root.after(
                0,
                self._update_progress,
                self.progress_bar_create,
                self.current_iso_label_var_create,
                0,
                100,
                "Copia de ISOs finalizada.",
            )

            # 6. Generar grub.cfg
            grub_cfg_path = os.path.join(grub_boot_dir, "grub", "grub.cfg")
            self.log_message(f"Generando {grub_cfg_path}...")
            grub_cfg_content = self.generate_grub_cfg_content(iso_filenames_on_usb)
            with open(grub_cfg_path, "w") as f:
                f.write(grub_cfg_content)
            self.log_message("grub.cfg generado.")

            # 7. Desmontar y finalizar
            self.log_message(f"Desmontando {TEMP_MOUNT_POINT}...")
            if not self.run_command(["umount", TEMP_MOUNT_POINT]):
                self.run_command(["sync"])
                time.sleep(1)
                if not self.run_command(["umount", TEMP_MOUNT_POINT]):
                    self.log_message(
                        f"ADVERTENCIA: No se pudo desmontar {TEMP_MOUNT_POINT}. Desmóntalo manualmente."
                    )

            self.log_message("¡Proceso de creación completado exitosamente!")
            messagebox.showinfo("Éxito", "El USB multiboot ha sido creado.")

        except Exception as e:
            self.log_message(f"ERROR EN CREACIÓN: {e}")
            messagebox.showerror("Error en Creación", f"Un error ocurrió: {e}")
            self.root.after(
                0,
                self._update_progress,
                self.progress_bar_create,
                self.current_iso_label_var_create,
                0,
                100,
                "Creación fallida.",
            )
        finally:
            if os.path.ismount(TEMP_MOUNT_POINT):
                self.run_command(
                    ["umount", "-lf", TEMP_MOUNT_POINT], check=False, log_cmd=False
                )
            self.create_button.config(state=tk.NORMAL)

    def generate_grub_cfg_content(self, iso_filenames_on_usb):
        cfg_parts = [
            "set timeout=20",
            "set default=0",
            "insmod all_video",
            "insmod gfxterm",
            "terminal_output gfxterm",
            "loadfont unicode",  # Añadir para mejor soporte de caracteres
        ]

        for iso_filename_on_usb in iso_filenames_on_usb:
            iso_title = (
                os.path.basename(iso_filename_on_usb)
                .replace(".iso", "")
                .replace("_", " ")
                .replace("-", " ")
            )

            entry = f"""
menuentry "Arrancar {iso_title}" {{
    set isofile="/isos/{iso_filename_on_usb}"
    echo "Cargando $isofile..."

    # Buscar la partición donde está el ISO (la raíz de GRUB debería ser esta partición)
    # search --no-floppy --file $isofile --set=rootusb
    # if [ x$rootusb = x ]; then
    #    echo "Error: No se encontró la partición con $isofile"
    #    sleep 5
    #    exit
    # fi
    # probe -u $rootusb --set=uuid_usb # Obtener UUID de la partición
    # set root=($rootusb) # Asegurar que GRUB usa esta partición como raíz para los paths

    loopback loop $isofile

    # Ubuntu/Debian (Casper)
    if [ -f (loop)/casper/vmlinuz ]; then
        echo "Detectado sistema tipo Casper (Ubuntu/Debian)..."
        linux (loop)/casper/vmlinuz boot=casper iso-scan/filename=$isofile quiet splash toram --
        initrd (loop)/casper/initrd.lz
    # Fedora/CentOS Live (isolinux)
    elif [ -f (loop)/isolinux/vmlinuz ] && [ -f (loop)/isolinux/initrd.img ]; then
        echo "Detectado sistema tipo ISOLINUX (Fedora/CentOS Live)..."
        linux (loop)/isolinux/vmlinuz iso-scan/filename=$isofile rd.live.image quiet splash
        initrd (loop)/isolinux/initrd.img
    # Arch Linux
    elif [ -f (loop)/arch/boot/x86_64/vmlinuz-linux ]; then
        echo "Detectado sistema tipo Arch Linux..."
        # El siguiente 'search' es crucial para Arch para encontrar el dispositivo correcto por etiqueta o UUID del ISO
        # Esto es complejo de generalizar. El usuario podría tener que ajustar 'archisobasedir' y 'archisodevice'
        # search --no-floppy --set=<y_bin_338>arch_iso_dev --label ARCH_YYYYMM # Reemplazar ARCH_YYYYMM con la etiqueta real del ISO de Arch
        # if [ x$arch_iso_dev != x ]; then
        #    linux (loop)/arch/boot/x86_64/vmlinuz-linux img_dev=$arch_iso_dev img_loop=$isofile archisobasedir=arch quiet splash
        # else
        #    # Fallback si la etiqueta no se encuentra, intentar con UUID de la partición actual (menos fiable para Arch)
        probe -u $root --set=uuid_current_part # $root es la partición de GRUB
        linux (loop)/arch/boot/x86_64/vmlinuz-linux img_dev=/dev/disk/by-uuid/$uuid_current_part img_loop=$isofile archisobasedir=arch quiet splash
        # fi
        initrd (loop)/arch/boot/intel-ucode.img (loop)/arch/boot/amd-ucode.img (loop)/arch/boot/x86_64/initramfs-linux.img
    # SystemRescueCD / otros basados en Syslinux/isolinux genéricos
    elif [ -f (loop)/syslinux/vmlinuz ] && ( [ -f (loop)/syslinux/initram.igz ] || [ -f (loop)/syslinux/initrd.img ] ); then
        echo "Detectado sistema tipo Syslinux genérico..."
        set kernel_path=(loop)/syslinux/vmlinuz
        set initrd_path=""
        if [ -f (loop)/syslinux/initram.igz ]; then set initrd_path=(loop)/syslinux/initram.igz; fi
        if [ -f (loop)/syslinux/initrd.img ]; then set initrd_path=(loop)/syslinux/initrd.img; fi

        # Parámetros comunes, pueden necesitar ajuste
        linux $kernel_path isoloop=$isofile noeject noprompt quiet splash
        initrd $initrd_path
    else
        echo "No se pudo determinar un método de arranque conocido para $isofile."
        echo "Puede que necesites crear una entrada manual en boot/grub/grub.cfg."
        echo "Presiona cualquier tecla para volver al menú..."
        read
    fi
}}"""
            cfg_parts.append(entry)

        return "\n".join(cfg_parts)

    def start_add_iso_to_usb_process(self):
        if not self.current_usb_device_path or not self.current_usb_partition1:
            messagebox.showerror(
                "Error", "Ningún USB compatible seleccionado para añadir ISOs."
            )
            return

        new_iso_path = filedialog.askopenfilename(
            title="Seleccionar Nuevo ISO para Añadir al USB",
            filetypes=(("Archivos ISO", "*.iso"),),
        )
        if not new_iso_path:
            return

        self.log_message(
            f"Iniciando proceso para añadir {os.path.basename(new_iso_path)} a {self.current_usb_device_path}"
        )
        self.add_to_usb_button.config(state=tk.DISABLED)
        self.remove_from_usb_button.config(state=tk.DISABLED)
        self.root.after(
            0,
            self._update_progress,
            self.progress_bar_manage,
            self.current_iso_label_var_manage,
            0,
            100,
            "Preparando para añadir ISO...",
        )

        thread = threading.Thread(
            target=self.worker_manage_iso,
            args=(
                self.current_usb_device_path,
                self.current_usb_partition1,
                "add",
                new_iso_path,
            ),
        )
        thread.daemon = True
        thread.start()

    def start_remove_iso_from_usb_process(self):
        if not self.current_usb_device_path or not self.current_usb_partition1:
            messagebox.showerror(
                "Error", "Ningún USB compatible seleccionado para quitar ISOs."
            )
            return

        selected_indices = self.mounted_iso_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning(
                "Advertencia", "Ningún ISO seleccionado del USB para quitar."
            )
            return

        iso_filename_to_remove = self.mounted_iso_listbox.get(selected_indices[0])

        if not messagebox.askyesno(
            "Confirmar Borrado",
            f"¿Seguro que quieres quitar '{iso_filename_to_remove}' del USB y actualizar GRUB?",
        ):
            return

        self.log_message(
            f"Iniciando proceso para quitar {iso_filename_to_remove} de {self.current_usb_device_path}"
        )
        self.add_to_usb_button.config(state=tk.DISABLED)
        self.remove_from_usb_button.config(state=tk.DISABLED)
        self.root.after(
            0,
            self._update_progress,
            self.progress_bar_manage,
            self.current_iso_label_var_manage,
            0,
            100,
            f"Quitando {iso_filename_to_remove}...",
        )

        thread = threading.Thread(
            target=self.worker_manage_iso,
            args=(
                self.current_usb_device_path,
                self.current_usb_partition1,
                "remove",
                iso_filename_to_remove,
            ),
        )
        thread.daemon = True
        thread.start()

    def worker_manage_iso(
        self, device_path, device_partition1, action, target_iso_param
    ):
        action_verb = "añadido" if action == "add" else "quitado"
        progress_bar_widget = self.progress_bar_manage
        label_var_widget = self.current_iso_label_var_manage
        success = False

        try:
            self.run_command(["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False)
            if not os.path.exists(TEMP_MOUNT_POINT):
                self.run_command(["mkdir", "-p", TEMP_MOUNT_POINT])
            if not self.run_command(["mount", device_partition1, TEMP_MOUNT_POINT]):
                raise Exception(
                    f"No se pudo montar {device_partition1} en {TEMP_MOUNT_POINT}"
                )

            isos_dir_on_usb = os.path.join(TEMP_MOUNT_POINT, "isos")
            grub_cfg_path = os.path.join(TEMP_MOUNT_POINT, "boot/grub/grub.cfg")

            if not os.path.isdir(isos_dir_on_usb):
                self.log_message(
                    f"Creando directorio {isos_dir_on_usb} ya que no existía."
                )
                self.run_command(["mkdir", "-p", isos_dir_on_usb])

            if action == "add":
                new_iso_path = target_iso_param
                iso_filename = os.path.basename(new_iso_path)
                dest_iso_path_on_usb = os.path.join(isos_dir_on_usb, iso_filename)

                # Comprobar si el ISO ya existe
                if os.path.exists(dest_iso_path_on_usb):
                    if not messagebox.askyesno(
                        "ISO Existente",
                        f"El archivo '{iso_filename}' ya existe en el USB. ¿Deseas sobrescribirlo?",
                    ):
                        self.log_message(
                            f"Adición de '{iso_filename}' cancelada por el usuario (ya existe)."
                        )
                        # Es importante limpiar el estado de la barra de progreso y botones aquí
                        self.root.after(
                            0,
                            self._update_progress,
                            progress_bar_widget,
                            label_var_widget,
                            0,
                            100,
                            f"Adición de '{iso_filename}' cancelada.",
                        )
                        # No lanzar excepción, simplemente no continuar con esta adición específica
                        # Hay que llamar a finally de alguna manera o reestructurar para que se actualice la UI
                        success = True  # Considerarlo un "éxito" en el sentido de que el flujo no rompió
                        # Pero la acción no se completó como se esperaba.
                        # Quizás un estado 'neutral' o 'cancelado' es mejor.
                        # Por ahora, lo dejamos como 'Operación finalizada'
                        return  # Salir de la función worker

                current_iso_info = f"Copiando: {iso_filename}"
                self.log_message(current_iso_info)

                file_size = os.path.getsize(new_iso_path)
                self.root.after(
                    0,
                    self._update_progress,
                    progress_bar_widget,
                    label_var_widget,
                    0,
                    file_size,
                    current_iso_info,
                )

                copied_bytes = 0
                buffer_size = 1024 * 1024
                with (
                    open(new_iso_path, "rb") as fsrc,
                    open(dest_iso_path_on_usb, "wb") as fdst,
                ):
                    while True:
                        chunk = fsrc.read(buffer_size)
                        if not chunk:
                            break
                        fdst.write(chunk)
                        copied_bytes += len(chunk)
                        self.root.after(
                            0,
                            self._update_progress,
                            progress_bar_widget,
                            label_var_widget,
                            copied_bytes,
                            None,
                            None,
                        )
                self.root.after(
                    0,
                    self._update_progress,
                    progress_bar_widget,
                    label_var_widget,
                    file_size,
                    None,
                    None,
                )
                self.log_message(f"ISO {iso_filename} copiado a {isos_dir_on_usb}")

            elif action == "remove":
                iso_filename_to_remove = target_iso_param
                path_to_remove_on_usb = os.path.join(
                    isos_dir_on_usb, iso_filename_to_remove
                )
                if os.path.exists(path_to_remove_on_usb):
                    os.remove(path_to_remove_on_usb)
                    self.log_message(
                        f"ISO {iso_filename_to_remove} eliminado de {isos_dir_on_usb}"
                    )
                else:
                    self.log_message(
                        f"Advertencia: ISO {iso_filename_to_remove} no encontrado en {isos_dir_on_usb} para eliminar."
                    )

            self.log_message("Actualizando grub.cfg...")
            current_isos_in_dir = [
                f for f in os.listdir(isos_dir_on_usb) if f.lower().endswith(".iso")
            ]

            if current_isos_in_dir:
                new_grub_content = self.generate_grub_cfg_content(current_isos_in_dir)
                with open(grub_cfg_path, "w") as f:
                    f.write(new_grub_content)
                self.log_message("grub.cfg actualizado con éxito.")
            else:
                with open(grub_cfg_path, "w") as f:
                    f.write(
                        "set timeout=5\nset default=0\n\nmenuentry 'No hay ISOs booteables' {\n  echo 'Por favor, añade archivos ISO al directorio /isos/ del USB.'\n  sleep 10\n}\n"
                    )
                self.log_message(
                    "Directorio de ISOs vacío. grub.cfg configurado con mensaje."
                )

            success = True
            self.log_message(
                f"ISO {target_iso_param if isinstance(target_iso_param, str) else os.path.basename(target_iso_param)} {action_verb} y GRUB actualizado."
            )

        except Exception as e:
            self.log_message(
                f"Error gestionando ISO ({action} {target_iso_param if isinstance(target_iso_param, str) else os.path.basename(target_iso_param)}): {e}"
            )
            messagebox.showerror("Error en Gestión", f"Ocurrió un error: {e}")
        finally:
            if os.path.ismount(TEMP_MOUNT_POINT):
                self.run_command(
                    ["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False
                )

            self.root.after(
                0, self.verify_and_load_isos_from_usb
            )  # Siempre refrescar la lista

            final_msg = "Operación finalizada." if success else "Operación fallida."
            if (
                action == "add"
                and not success
                and "cancelada por el usuario"
                in self.current_iso_label_var_manage.get()
            ):  # Caso especial de cancelación
                final_msg = self.current_iso_label_var_manage.get()

            self.root.after(
                0,
                self._update_progress,
                progress_bar_widget,
                label_var_widget,
                0,
                100,
                final_msg,
            )
            # La reactivación de botones ahora se maneja dentro de verify_and_load_isos_from_usb via _update_manage_ui_state


if __name__ == "__main__":
    main_window = tk.Tk()
    app = MultibootUSBApp(main_window)
    main_window.mainloop()
