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


def format_time_remaining(seconds):
    """Formatea segundos a un string HH:MM:SS o MM:SS."""
    if seconds is None or seconds == float("inf") or seconds < 0:
        return "Calculando..."
    if seconds < 1 and seconds > 0:
        return "< 1 seg"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


class MultibootUSBApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Creador y Gestor USB Multiboot para Linux (exFAT)")
        self.root.geometry("750x800")

        self.iso_files = []
        self.current_usb_device_path = None
        self.current_usb_partition1 = None

        self.create_op_total_bytes_all_isos = 0
        self.create_op_copied_bytes_all_isos = 0
        self.create_op_start_time_overall = 0

        self.manage_op_total_bytes_current_iso = 0
        self.manage_op_start_time_current_iso = 0

        log_frame_outer = ttk.Frame(self.root)
        log_frame_inner = ttk.LabelFrame(log_frame_outer, text="Log de Operaciones")
        self.log_area = scrolledtext.ScrolledText(
            log_frame_inner, wrap=tk.WORD, height=8, state=tk.DISABLED
        )
        self.log_area.pack(padx=5, pady=5, fill="both", expand=True)
        log_frame_inner.pack(padx=10, pady=10, fill="both", expand=True)

        if os.geteuid() != 0:
            messagebox.showerror(
                "Error de Permisos", "Este script debe ejecutarse como root (con sudo)."
            )
            self.root.destroy()
            return
        if not self.check_dependencies():
            self.root.destroy()
            return

        top_usb_frame = ttk.LabelFrame(self.root, text="Dispositivo USB")
        top_usb_frame.pack(padx=10, pady=10, fill="x")
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

        self.notebook = ttk.Notebook(self.root)
        create_tab = ttk.Frame(self.notebook)
        self.notebook.add(create_tab, text="Crear Nuevo USB Multiboot (exFAT)")
        self._populate_create_tab(create_tab)
        manage_tab = ttk.Frame(self.notebook)
        self.notebook.add(manage_tab, text="Gestionar USB Existente (exFAT)")
        self._populate_manage_tab(manage_tab)

        self.notebook.pack(padx=10, pady=10, fill="both", expand=True)
        log_frame_outer.pack(padx=0, pady=0, fill="both", expand=True)

        self.populate_usb_devices()
        self._update_manage_ui_state(is_compatible=False)

    def get_downloads_folder(self):
        home_dir = os.path.expanduser("~")
        # Priorizar el nombre en español
        downloads_path_es = os.path.join(home_dir, "Descargas")
        if os.path.isdir(downloads_path_es):
            return downloads_path_es

        # Fallback al nombre en inglés
        downloads_path_en = os.path.join(home_dir, "Downloads")
        if os.path.isdir(downloads_path_en):
            return downloads_path_en

        # Si ninguno existe, simplemente devolver el directorio home del usuario
        self.log_message(
            f"No se encontró 'Descargas' ni 'Downloads', usando directorio home: {home_dir}"
        )
        return home_dir

    def _populate_create_tab(self, parent_tab):
        iso_frame = ttk.LabelFrame(
            parent_tab, text="1. Seleccionar Archivos ISO para Nuevo USB"
        )
        iso_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.iso_listbox_create = tk.Listbox(
            iso_frame, selectmode=tk.MULTIPLE, width=60, height=5
        )
        self.iso_listbox_create.pack(
            padx=5, pady=5, side=tk.LEFT, fill="both", expand=True
        )
        iso_button_frame = ttk.Frame(iso_frame)
        iso_button_frame.pack(side=tk.LEFT, padx=5, pady=5, fill="y")
        ttk.Button(
            iso_button_frame,
            text="Añadir ISO(s)",
            command=self.add_iso_for_create,  # Modificado
        ).pack(pady=5, fill="x")
        ttk.Button(
            iso_button_frame, text="Quitar ISO(s)", command=self.remove_iso_for_create
        ).pack(pady=5, fill="x")

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
        ttk.Label(
            self.progress_info_frame_create,
            textvariable=self.current_iso_label_var_create,
            anchor="w",
        ).pack(fill="x")
        self.progress_bar_create = ttk.Progressbar(
            self.progress_info_frame_create,
            orient="horizontal",
            length=300,
            mode="determinate",
        )
        self.progress_bar_create.pack(fill="x", pady=(0, 5))
        self.speed_label_var_create = tk.StringVar(value="Velocidad: N/A")
        ttk.Label(
            self.progress_info_frame_create,
            textvariable=self.speed_label_var_create,
            anchor="w",
        ).pack(fill="x")
        self.eta_current_iso_label_var_create = tk.StringVar(
            value="Restante (ISO actual): N/A"
        )
        ttk.Label(
            self.progress_info_frame_create,
            textvariable=self.eta_current_iso_label_var_create,
            anchor="w",
        ).pack(fill="x")
        self.eta_total_label_var_create = tk.StringVar(value="Restante (Total): N/A")
        ttk.Label(
            self.progress_info_frame_create,
            textvariable=self.eta_total_label_var_create,
            anchor="w",
        ).pack(fill="x")

    def _populate_manage_tab(self, parent_tab):
        ttk.Label(
            parent_tab,
            text="Selecciona un dispositivo USB. Si es compatible (formato exFAT y estructura de esta app), se listarán sus ISOs.",
            wraplength=600,
        ).pack(padx=10, pady=10)
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

        manage_actions_frame = ttk.LabelFrame(parent_tab, text="Acciones de Gestión")
        manage_actions_frame.pack(padx=10, pady=10, fill="x")
        self.add_to_usb_button = ttk.Button(
            manage_actions_frame,
            text="Añadir Nuevo ISO al USB",
            command=self.start_add_iso_to_usb_process,  # Modificado
        )
        self.add_to_usb_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.remove_from_usb_button = ttk.Button(
            manage_actions_frame,
            text="Quitar ISO Seleccionado del USB",
            command=self.start_remove_iso_from_usb_process,
        )
        self.remove_from_usb_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.progress_info_frame_manage = ttk.Frame(parent_tab)
        self.progress_info_frame_manage.pack(fill="x", padx=10, pady=(5, 10))
        self.current_iso_label_var_manage = tk.StringVar(value="Progreso de copia: N/A")
        ttk.Label(
            self.progress_info_frame_manage,
            textvariable=self.current_iso_label_var_manage,
            anchor="w",
        ).pack(fill="x")
        self.progress_bar_manage = ttk.Progressbar(
            self.progress_info_frame_manage,
            orient="horizontal",
            length=300,
            mode="determinate",
        )
        self.progress_bar_manage.pack(fill="x", pady=(0, 5))
        self.speed_label_var_manage = tk.StringVar(value="Velocidad: N/A")
        ttk.Label(
            self.progress_info_frame_manage,
            textvariable=self.speed_label_var_manage,
            anchor="w",
        ).pack(fill="x")
        self.eta_current_iso_label_var_manage = tk.StringVar(
            value="Restante (ISO actual): N/A"
        )
        ttk.Label(
            self.progress_info_frame_manage,
            textvariable=self.eta_current_iso_label_var_manage,
            anchor="w",
        ).pack(fill="x")

    def log_message(self, message):
        if hasattr(self, "log_area") and self.log_area:
            self.log_area.configure(state=tk.NORMAL)
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.configure(state=tk.DISABLED)
            self.log_area.see(tk.END)
            if hasattr(self, "root") and self.root.winfo_exists():
                self.root.update_idletasks()
        else:
            print(f"LOG (pre-GUI): {message}")

    def run_command(self, command_list, check=True, capture_output=False, log_cmd=True):
        # ... (sin cambios) ...
        if log_cmd:
            self.log_message(f"Ejecutando: {' '.join(command_list)}")
        try:
            process = subprocess.run(
                command_list,
                check=check,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if process.stdout and log_cmd:
                self.log_message(f"Salida: {process.stdout.strip()}")
            if process.stderr and log_cmd:
                self.log_message(f"Stderr: {process.stderr.strip()}")
            if check and process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode,
                    command_list,
                    output=process.stdout,
                    stderr=process.stderr,
                )
            return process.stdout.strip() if capture_output else True
        except subprocess.CalledProcessError as e:
            self.log_message(
                f"Error ejecutando comando '{' '.join(e.cmd)}': Código {e.returncode}"
            )
            if e.stdout:
                self.log_message(f"  Stdout del error: {e.stdout.strip()}")
            if e.stderr:
                self.log_message(f"  Stderr del error: {e.stderr.strip()}")
            return False
        except FileNotFoundError:
            self.log_message(f"Error: Comando '{command_list[0]}' no encontrado.")
            return False

    def check_dependencies(self):
        # ... (sin cambios, ya incluye mkfs.exfat) ...
        dependencies = [
            "lsblk",
            "parted",
            "mkfs.exfat",
            "grub-install",
            "umount",
            "mount",
            "partprobe",
        ]
        missing = []
        for dep in dependencies:
            if shutil.which(dep) is None:
                missing.append(dep)
        if missing:
            messagebox.showerror(
                "Dependencias Faltantes",
                f"Las sig. dependencias no se encontraron: {', '.join(missing)}.\n"
                "Usa install_dependencies.sh o instálalas manualmente (ej: exfatprogs).",
            )
            return False
        self.log_message("Dependencias necesarias presentes.")
        return True

    def populate_usb_devices(self):
        # ... (sin cambios) ...
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
                self.on_usb_selected()
            else:
                self.log_message("No se encontraron dispositivos USB.")
                self._update_manage_ui_state(is_compatible=False)
        except Exception as e:
            self.log_message(f"Error al listar dispositivos: {e}")
            messagebox.showerror("Error", f"{e}")
            self._update_manage_ui_state(is_compatible=False)

    def add_iso_for_create(self):
        # MODIFICADO para usar initialdir
        initial_dir = self.get_downloads_folder()
        self.log_message(f"Abriendo diálogo de ISOs en: {initial_dir}")
        filepaths = filedialog.askopenfilenames(
            initialdir=initial_dir,  # <--- AÑADIDO
            title="Seleccionar Archivos ISO para Nuevo USB",
            filetypes=(("Archivos ISO", "*.iso"), ("Todos los archivos", "*.*")),
        )
        if filepaths:
            count_added = 0
            for filepath in filepaths:
                if filepath not in self.iso_files:
                    if os.path.basename(filepath) not in self.iso_listbox_create.get(
                        0, tk.END
                    ):
                        self.iso_files.append(filepath)
                        self.iso_listbox_create.insert(
                            tk.END, os.path.basename(filepath)
                        )
                        count_added += 1
                    else:
                        self.log_message(
                            f"ISO {os.path.basename(filepath)} ya está en la lista de creación."
                        )
            if count_added > 0:
                self.log_message(f"{count_added} ISO(s) nuevos añadidos para creación.")

    def remove_iso_for_create(self):
        # ... (sin cambios) ...
        selected_indices = self.iso_listbox_create.curselection()
        if not selected_indices:
            return
        for index in reversed(selected_indices):
            iso_to_remove_display = self.iso_listbox_create.get(index)
            paths_to_remove = [
                p
                for p in self.iso_files
                if os.path.basename(p) == iso_to_remove_display
            ]
            for p_rem in paths_to_remove:
                self.iso_files.remove(p_rem)
            self.iso_listbox_create.delete(index)
            self.log_message(f"ISO quitado de creación: {iso_to_remove_display}")

    def _get_selected_usb_paths(self):
        # ... (sin cambios) ...
        selected_usb_display = self.usb_var.get()
        if not selected_usb_display:
            return None, None
        device_path = selected_usb_display.split(" - ")[0]
        partition1 = device_path + "1"
        base_name = os.path.basename(device_path)
        if (
            "mmcblk" in base_name
            and "p" not in base_name
            and not base_name.endswith("p")
        ):
            partition1 = device_path + "p1"
        elif (
            ("loop" in base_name or "nvme" in base_name)
            and "p" not in base_name
            and not base_name.endswith("p")
        ):
            if "nvme" in base_name and "n" in base_name:
                partition1 = device_path + "p1"
            elif "loop" in base_name:
                partition1 = device_path + "p1"
        return device_path, partition1

    def on_usb_selected(self, event=None):
        # ... (sin cambios) ...
        self.current_usb_device_path, self.current_usb_partition1 = (
            self._get_selected_usb_paths()
        )
        if self.current_usb_device_path:
            self.log_message(
                f"USB seleccionado: {self.current_usb_device_path}, Partición: {self.current_usb_partition1}. Verificando..."
            )
            self.verify_and_load_isos_from_usb()
        else:
            self._update_manage_ui_state(is_compatible=False)

    def _update_manage_ui_state(self, is_compatible, isos_found=False):
        # ... (sin cambios) ...
        if not hasattr(self, "add_to_usb_button"):
            return
        state_normal_if_compat = tk.NORMAL if is_compatible else tk.DISABLED
        self.add_to_usb_button.config(state=state_normal_if_compat)
        self.refresh_mounted_isos_button.config(state=state_normal_if_compat)
        self.remove_from_usb_button.config(
            state=tk.NORMAL if is_compatible and isos_found else tk.DISABLED
        )  # Quitado self.mounted_iso_listbox.size() > 0 para que se active si hay isos_found
        if not is_compatible and hasattr(self, "mounted_iso_listbox"):
            self.mounted_iso_listbox.delete(0, tk.END)

    def verify_and_load_isos_from_usb(self):
        # ... (sin cambios) ...
        if not self.current_usb_partition1:
            self._update_manage_ui_state(is_compatible=False)
            self.log_message("Partición USB no válida.")
            return False
        if hasattr(self, "mounted_iso_listbox"):
            self.mounted_iso_listbox.delete(0, tk.END)
        self.log_message(
            f"Verificando {self.current_usb_partition1} en {TEMP_MOUNT_POINT}..."
        )
        self.run_command(["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False)
        if not os.path.exists(TEMP_MOUNT_POINT):
            if not self.run_command(["mkdir", "-p", TEMP_MOUNT_POINT]):
                self.log_message(f"Error: No se pudo crear {TEMP_MOUNT_POINT}.")
                self._update_manage_ui_state(is_compatible=False)
                return False
        is_compatible_usb = False
        isos_on_device = []
        try:
            mount_success = False
            if self.run_command(
                ["mount", "-t", "exfat", self.current_usb_partition1, TEMP_MOUNT_POINT],
                check=False,
            ):
                mount_success = True
            else:
                self.log_message(
                    f"Montaje exfat falló, intentando auto para {self.current_usb_partition1}..."
                )
                if self.run_command(
                    ["mount", self.current_usb_partition1, TEMP_MOUNT_POINT]
                ):
                    mount_success = True
            if mount_success:
                grub_cfg_path = os.path.join(TEMP_MOUNT_POINT, "boot/grub/grub.cfg")
                isos_dir = os.path.join(TEMP_MOUNT_POINT, "isos")
                if os.path.exists(grub_cfg_path) and os.path.isdir(isos_dir):
                    self.log_message(f"USB {self.current_usb_device_path} compatible.")
                    is_compatible_usb = True
                    for item in os.listdir(isos_dir):
                        if item.lower().endswith(".iso"):
                            isos_on_device.append(item)
                            self.mounted_iso_listbox.insert(tk.END, item)
                    if isos_on_device:
                        self.log_message(f"ISOs: {', '.join(isos_on_device)}")
                    else:
                        self.log_message(f"Directorio 'isos' vacío.")
                else:
                    self.log_message(
                        f"USB {self.current_usb_device_path} no compatible (falta grub.cfg o /isos)."
                    )
            else:
                self.log_message(f"No se pudo montar {self.current_usb_partition1}.")
        finally:
            if os.path.ismount(TEMP_MOUNT_POINT):
                self.run_command(["umount", TEMP_MOUNT_POINT], check=False)
        self._update_manage_ui_state(is_compatible_usb, isos_found=bool(isos_on_device))
        return is_compatible_usb

    def refresh_isos_on_selected_usb(self):
        # ... (sin cambios) ...
        if self.current_usb_device_path:
            self.verify_and_load_isos_from_usb()
        else:
            messagebox.showinfo("Información", "Selecciona un USB primero.")

    def _update_progress_and_eta(
        self,
        bar_widget,
        label_var_widget,
        speed_var_widget,
        eta_curr_var_widget,
        eta_total_var_widget,
        copied_val,
        max_val=None,
        label_text=None,
        speed_bytes_sec=None,
        eta_curr_seconds=None,
        eta_total_seconds=None,
    ):
        # ... (sin cambios) ...
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return
        if bar_widget:
            if max_val is not None:
                bar_widget.config(maximum=max_val)
            bar_widget.config(value=copied_val)
        if label_var_widget and label_text is not None:
            label_var_widget.set(label_text)
        if speed_var_widget:
            if speed_bytes_sec is not None and speed_bytes_sec > 0.001:
                speed_mb_sec = speed_bytes_sec / (1024 * 1024)
                speed_var_widget.set(f"Velocidad: {speed_mb_sec:.2f} MB/s")
            elif speed_bytes_sec == 0:
                speed_var_widget.set("Velocidad: Calculando...")
            else:
                speed_var_widget.set("Velocidad: N/A")
        if eta_curr_var_widget:
            eta_curr_var_widget.set(
                f"Restante (ISO actual): {format_time_remaining(eta_curr_seconds)}"
            )
        if eta_total_var_widget:
            eta_total_var_widget.set(
                f"Restante (Total): {format_time_remaining(eta_total_seconds)}"
            )

    def start_creation_process(self):
        # ... (sin cambios) ...
        device_path, _ = self._get_selected_usb_paths()
        if not device_path:
            messagebox.showerror("Error", "Selecciona un dispositivo USB.")
            return
        if not self.iso_files:
            messagebox.showerror("Error", "Añade al menos un archivo ISO.")
            return
        self.create_op_total_bytes_all_isos = 0
        for iso_f_path in self.iso_files:
            try:
                self.create_op_total_bytes_all_isos += os.path.getsize(iso_f_path)
            except OSError:
                messagebox.showerror(
                    "Error", f"No se pudo obtener tamaño de {iso_f_path}"
                )
                return
        self.create_op_copied_bytes_all_isos = 0
        self.create_op_start_time_overall = 0
        confirm_msg = (
            f"¡ADVERTENCIA! Se formateará {device_path} como exFAT.\n"
            f"TODOS LOS DATOS SE PERDERÁN.\n\n¿Continuar?"
        )
        if messagebox.askyesno("Confirmar Formateo exFAT", confirm_msg, icon="warning"):
            self.create_button.config(state=tk.DISABLED)
            self.log_message("Iniciando creación del USB (exFAT)...")
            self.root.after(
                0,
                self._update_progress_and_eta,
                self.progress_bar_create,
                self.current_iso_label_var_create,
                self.speed_label_var_create,
                self.eta_current_iso_label_var_create,
                self.eta_total_label_var_create,
                0,
                100,
                "Iniciando...",
                None,
                None,
                None,
            )
            thread = threading.Thread(
                target=self.create_multiboot_usb_worker, args=(list(self.iso_files),)
            )
            thread.daemon = True
            thread.start()
        else:
            self.log_message("Creación cancelada.")

    def create_multiboot_usb_worker(self, iso_list_paths):
        # CORREGIDO EL TYPO AQUÍ
        # ... (resto del worker como en la respuesta anterior, con el typo TEMP_MONT_POINT corregido a TEMP_MOUNT_POINT)
        device_path, device_partition1 = (
            self.current_usb_device_path,
            self.current_usb_partition1,
        )
        if not device_path or not device_partition1:
            self.log_message("Error worker: Dispositivo/Partición USB no definidos.")
            self.root.after(
                0,
                self._update_progress_and_eta,
                self.progress_bar_create,
                self.current_iso_label_var_create,
                self.speed_label_var_create,
                self.eta_current_iso_label_var_create,
                self.eta_total_label_var_create,
                0,
                100,
                "Error de dispositivo",
                None,
                None,
                None,
            )
            if hasattr(self, "create_button"):
                self.create_button.config(state=tk.NORMAL)
                return

        final_status_msg = "Creación fallida (exFAT)."
        try:
            self.log_message(
                f"Worker: Usando {device_path}, part {device_partition1} con exFAT"
            )
            # 1. Desmontar
            self.log_message(f"Desmontando particiones en {device_path}...")
            try:
                result = self.run_command(
                    ["lsblk", "-no", "MOUNTPOINT,NAME", device_path],
                    capture_output=True,
                    log_cmd=False,
                )
                if result and isinstance(result, str) and result.strip():
                    for line in result.strip().split("\n"):
                        parts = line.split()
                        if len(parts) > 1 and parts[0] and parts[0] != "[SWAP]":
                            mountpoint = parts[0]
                            part_name_suffix = parts[-1].split("/")[-1]
                            partition_to_umount = f"/dev/{part_name_suffix}"
                            self.log_message(
                                f"Intentando desmontar {partition_to_umount} de {mountpoint}..."
                            )
                            self.run_command(
                                ["umount", partition_to_umount], check=False
                            )
                            self.run_command(
                                ["umount", "-lf", partition_to_umount], check=False
                            )
            except Exception as e:
                self.log_message(f"Error durante desmontaje (puede ser normal): {e}")

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
                    "ntfs",
                    "1MiB",
                    "100%",
                ]
            ):
                raise Exception("Fallo mkpart (tipo ntfs para exFAT ID)")
            if not self.run_command(
                ["parted", "-s", device_path, "set", "1", "boot", "on"]
            ):
                raise Exception("Fallo set boot on")
            self.log_message("Releyendo tabla...")
            time.sleep(3)
            self.run_command(["partprobe", device_path], check=False)
            time.sleep(3)
            self.log_message(f"Formateando {device_partition1} como exFAT...")
            if not self.run_command(
                ["mkfs.exfat", "-n", "MULTIBOOT", device_partition1]
            ):
                time.sleep(5)
                self.run_command(["partprobe", device_path], check=False)
                time.sleep(2)
                if not self.run_command(
                    ["mkfs.exfat", "-n", "MULTIBOOT", device_partition1]
                ):
                    raise Exception(f"Fallo formatear {device_partition1} exFAT")

            # 3. Montar
            self.run_command(
                ["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False
            )  # Correcto
            if not os.path.exists(TEMP_MOUNT_POINT):
                self.run_command(["mkdir", "-p", TEMP_MOUNT_POINT])  # Correcto
            mount_cmd_exfat = [
                "mount",
                "-t",
                "exfat",
                device_partition1,
                TEMP_MOUNT_POINT,
            ]  # CORRECTO
            mount_cmd_auto = ["mount", device_partition1, TEMP_MOUNT_POINT]  # Correcto
            if not self.run_command(mount_cmd_exfat, check=False):
                if not self.run_command(mount_cmd_auto):
                    raise Exception(f"Fallo mount {device_partition1}")

            # 4. Instalar GRUB
            grub_boot_dir = os.path.join(TEMP_MOUNT_POINT, "boot")  # Correcto
            grub_install_cmd = [
                "grub-install",
                f"--boot-directory={grub_boot_dir}",
                "--target=i386-pc",
                "--no-floppy",
                device_path,
            ]
            if not self.run_command(grub_install_cmd):
                grub_install_cmd.append("--force")
                if not self.run_command(grub_install_cmd):
                    raise Exception(f"Fallo instalar GRUB2 en {device_path}")

            # 5. Copiar ISOs (con lógica ETA completa)
            self.create_op_start_time_overall = time.monotonic()
            self.create_op_copied_bytes_all_isos = 0
            isos_dir = os.path.join(TEMP_MOUNT_POINT, "isos")
            self.run_command(["mkdir", "-p", isos_dir])  # Correcto
            iso_filenames_on_usb = []
            for idx, iso_path in enumerate(iso_list_paths):
                iso_filename = os.path.basename(iso_path)
                dest_iso_path = os.path.join(isos_dir, iso_filename)
                text = f"Copiando ({idx + 1}/{len(iso_list_paths)}): {iso_filename}"
                start_iso_t = time.monotonic()
                size_iso = os.path.getsize(iso_path)
                copied_iso = 0
                self.root.after(
                    0,
                    self._update_progress_and_eta,
                    self.progress_bar_create,
                    self.current_iso_label_var_create,
                    self.speed_label_var_create,
                    self.eta_current_iso_label_var_create,
                    self.eta_total_label_var_create,
                    0,
                    size_iso,
                    text,
                    0,
                    None,
                    None,
                )
                buf = 1024 * 1024
                last_update_t = time.monotonic()
                try:
                    with (
                        open(iso_path, "rb") as fsrc,
                        open(dest_iso_path, "wb") as fdst,
                    ):
                        while True:
                            chunk = fsrc.read(buf)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            copied_iso += len(chunk)
                            self.create_op_copied_bytes_all_isos += len(chunk)
                            now = time.monotonic()
                            if now - last_update_t >= 0.5:
                                el_iso = max(0.1, now - start_iso_t)
                                sp_iso = copied_iso / el_iso if el_iso > 0 else 0
                                eta_iso = (
                                    (size_iso - copied_iso) / sp_iso
                                    if sp_iso > 0
                                    else float("inf")
                                )
                                el_all = max(
                                    0.1, now - self.create_op_start_time_overall
                                )
                                sp_all = (
                                    self.create_op_copied_bytes_all_isos / el_all
                                    if el_all > 0
                                    else 0
                                )
                                eta_all = (
                                    (
                                        self.create_op_total_bytes_all_isos
                                        - self.create_op_copied_bytes_all_isos
                                    )
                                    / sp_all
                                    if sp_all > 0
                                    else float("inf")
                                )
                                self.root.after(
                                    0,
                                    self._update_progress_and_eta,
                                    self.progress_bar_create,
                                    None,
                                    self.speed_label_var_create,
                                    self.eta_current_iso_label_var_create,
                                    self.eta_total_label_var_create,
                                    copied_iso,
                                    None,
                                    None,
                                    sp_iso,
                                    eta_iso,
                                    eta_all,
                                )
                                last_update_t = now
                    iso_filenames_on_usb.append(iso_filename)
                    self.root.after(
                        0,
                        self._update_progress_and_eta,
                        self.progress_bar_create,
                        None,
                        self.speed_label_var_create,
                        self.eta_current_iso_label_var_create,
                        None,
                        size_iso,
                        None,
                        None,
                        None,
                        0,
                        None,
                    )
                except Exception as e:
                    self.log_message(f"Error copiando {iso_filename}: {e}")
            if not iso_filenames_on_usb:
                raise Exception("No se copió ningún ISO.")

            # 6. Generar grub.cfg
            grub_cfg_path = os.path.join(grub_boot_dir, "grub", "grub.cfg")
            with open(grub_cfg_path, "w") as f:
                f.write(self.generate_grub_cfg_content(iso_filenames_on_usb))
            self.log_message("grub.cfg generado.")

            # 7. Desmontar
            if not self.run_command(
                ["umount", TEMP_MOUNT_POINT], check=False
            ):  # Correcto
                self.run_command(["sync"])
                time.sleep(1)
                self.run_command(
                    ["umount", "-lf", TEMP_MOUNT_POINT], check=False
                )  # Correcto
            final_status_msg = "¡Creación (exFAT) completada!"
            self.log_message(final_status_msg)
            messagebox.showinfo("Éxito", "USB multiboot (exFAT) creado.")
        except Exception as e:
            self.log_message(f"ERROR CREACIÓN (exFAT): {e}")
            messagebox.showerror("Error Creación", f"{e}")
        finally:
            if os.path.ismount(TEMP_MOUNT_POINT):
                self.run_command(
                    ["umount", "-lf", TEMP_MOUNT_POINT], check=False, log_cmd=False
                )  # Correcto
            self.root.after(
                0,
                self._update_progress_and_eta,
                self.progress_bar_create,
                self.current_iso_label_var_create,
                self.speed_label_var_create,
                self.eta_current_iso_label_var_create,
                self.eta_total_label_var_create,
                0,
                100,
                final_status_msg,
                None,
                None,
                None,
            )
            if hasattr(self, "create_button"):
                self.create_button.config(state=tk.NORMAL)

    def generate_grub_cfg_content(self, iso_filenames_on_usb):
        cfg_parts = [
            "set timeout=20",
            "set default=0",
            "insmod part_msdos",
            "insmod exfat",
            "insmod all_video",
            "insmod gfxterm",
            "terminal_output gfxterm",
            "loadfont unicode",
            "",
        ]

        for (
            iso_filename
        ) in iso_filenames_on_usb:  # Cambié el nombre de la variable aquí para claridad
            title = iso_filename.replace(".iso", "").replace("_", " ").replace("-", " ")
            grub_iso_path = f"/isos/{iso_filename}"

            entry = [
                f"""menuentry "Arrancar {title}" {{""",
                f"""    set isofile="{grub_iso_path}" """,
                f"""    echo "Cargando $isofile..." """,
                f"""    loopback loop $isofile""",
            ]

            # ----- INICIO DE LÓGICA ESPECÍFICA PARA CLONEZILLA -----
            # Asumimos que iso_filename es algo como "clonezilla-live-...amd64.iso"
            # Si solo hay un ISO y es Clonezilla, esta lógica se aplicará.
            # Si tienes más ISOs, necesitarías una forma de identificar que este es Clonezilla.
            # Por ahora, como dijiste que solo tienes Clonezilla, esta será la única entrada generada.

            if (
                "clonezilla" in iso_filename.lower()
            ):  # Condición simple para aplicar esta config
                self.log_message(
                    f"Generando entrada específica para Clonezilla: {iso_filename}"
                )
                entry.extend(
                    [
                        f"""    echo "Intentando arranque específico para Clonezilla..." """,
                        # Parámetros comunes para Clonezilla. 'findiso=' es crucial.
                        # La ruta al kernel/initrd suele ser /live/
                        f"""    linux (loop)/live/vmlinuz boot=live union=overlay username=user config components quiet noswap edd=on nomodeset findiso=${{isofile}} toram --""",
                        f"""    initrd (loop)/live/initrd.img""",
                    ]
                )
            else:
                # Si tuvieras otros ISOs, aquí volvería la lógica if/elif más genérica
                # o un mensaje de error si no es Clonezilla y no tienes otra lógica.
                # Por ahora, para la prueba con solo Clonezilla, podemos poner un mensaje de error
                # si el ISO no parece ser Clonezilla.
                entry.extend(
                    [
                        f"""    echo "Este ISO no parece ser Clonezilla y no hay otra configuración." """,
                        f"""    echo "Presiona una tecla..." """,
                        f"""    read""",
                    ]
                )
            # ----- FIN DE LÓGICA ESPECÍFICA PARA CLONEZILLA -----

            entry.append(f"""}}""")
            cfg_parts.extend(entry)
            cfg_parts.append("")
        return "\n".join(cfg_parts)

    def start_add_iso_to_usb_process(self):
        # MODIFICADO para usar initialdir
        if not self.current_usb_device_path or not self.current_usb_partition1:
            messagebox.showerror("Error", "Ningún USB compatible.")
            return

        initial_dir = self.get_downloads_folder()
        self.log_message(f"Abriendo diálogo para añadir ISO en: {initial_dir}")
        new_iso_path = filedialog.askopenfilename(
            initialdir=initial_dir,  # <--- AÑADIDO
            title="Seleccionar ISO para Añadir",
            filetypes=(("Archivos ISO", "*.iso"),),
        )
        if not new_iso_path:
            return
        try:
            self.manage_op_total_bytes_current_iso = os.path.getsize(new_iso_path)
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo leer {new_iso_path}: {e}")
            return
        self.manage_op_start_time_current_iso = 0
        self.log_message(
            f"Añadiendo {os.path.basename(new_iso_path)} a {self.current_usb_device_path}"
        )
        self.add_to_usb_button.config(state=tk.DISABLED)
        self.remove_from_usb_button.config(state=tk.DISABLED)
        self.root.after(
            0,
            self._update_progress_and_eta,
            self.progress_bar_manage,
            self.current_iso_label_var_manage,
            self.speed_label_var_manage,
            self.eta_current_iso_label_var_manage,
            None,
            0,
            100,
            "Preparando...",
            None,
            None,
            None,
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
        # ... (sin cambios) ...
        if not self.current_usb_device_path:
            messagebox.showerror("Error", "Ningún USB compatible.")
            return
        sel = self.mounted_iso_listbox.curselection()
        if not sel:
            messagebox.showwarning("Advertencia", "Ningún ISO seleccionado.")
            return
        iso_to_remove = self.mounted_iso_listbox.get(sel[0])
        if not messagebox.askyesno(
            "Confirmar", f"¿Quitar '{iso_to_remove}' y actualizar GRUB?"
        ):
            return
        self.log_message(f"Quitando {iso_to_remove} de {self.current_usb_device_path}")
        self.add_to_usb_button.config(state=tk.DISABLED)
        self.remove_from_usb_button.config(state=tk.DISABLED)
        self.root.after(
            0,
            self._update_progress_and_eta,
            self.progress_bar_manage,
            self.current_iso_label_var_manage,
            self.speed_label_var_manage,
            self.eta_current_iso_label_var_manage,
            None,
            0,
            100,
            f"Quitando {iso_to_remove}...",
            None,
            None,
            None,
        )
        thread = threading.Thread(
            target=self.worker_manage_iso,
            args=(
                self.current_usb_device_path,
                self.current_usb_partition1,
                "remove",
                iso_to_remove,
            ),
        )
        thread.daemon = True
        thread.start()

    def worker_manage_iso(self, device_path, device_partition1, action, target_param):
        # ... (sin cambios, ya incluye lógica ETA para 'add')
        verb = "añadido" if action == "add" else "quitado"
        bar, lbl, spd, eta_curr = (
            self.progress_bar_manage,
            self.current_iso_label_var_manage,
            self.speed_label_var_manage,
            self.eta_current_iso_label_var_manage,
        )
        ok = False
        final_msg = "Operación fallida."
        try:
            self.run_command(["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False)
            if not os.path.exists(TEMP_MOUNT_POINT):
                self.run_command(["mkdir", "-p", TEMP_MOUNT_POINT])

            mount_cmd_exfat = [
                "mount",
                "-t",
                "exfat",
                device_partition1,
                TEMP_MOUNT_POINT,
            ]
            mount_cmd_auto = ["mount", device_partition1, TEMP_MOUNT_POINT]
            if not self.run_command(mount_cmd_exfat, check=False):
                if not self.run_command(mount_cmd_auto):
                    raise Exception(f"No se pudo montar {device_partition1}")

            isos_dir = os.path.join(TEMP_MOUNT_POINT, "isos")
            grub_cfg = os.path.join(TEMP_MOUNT_POINT, "boot/grub/grub.cfg")
            if not os.path.isdir(isos_dir):
                self.run_command(["mkdir", "-p", isos_dir])

            if action == "add":
                iso_path, iso_name = target_param, os.path.basename(target_param)
                dest_path = os.path.join(isos_dir, iso_name)
                if os.path.exists(dest_path) and not messagebox.askyesno(
                    "Sobrescribir", f"'{iso_name}' ya existe. ¿Sobrescribir?"
                ):
                    self.log_message(f"Adición de '{iso_name}' cancelada.")
                    final_msg = "Adición cancelada."
                    raise Exception("Cancelled by user")

                text = f"Copiando: {iso_name}"
                self.manage_op_start_time_current_iso = time.monotonic()
                copied = 0
                self.root.after(
                    0,
                    self._update_progress_and_eta,
                    bar,
                    lbl,
                    spd,
                    eta_curr,
                    None,
                    0,
                    self.manage_op_total_bytes_current_iso,
                    text,
                    0,
                    None,
                    None,
                )
                buf = 1024 * 1024
                last_t = time.monotonic()
                with open(iso_path, "rb") as fsrc, open(dest_path, "wb") as fdst:
                    while True:
                        chunk = fsrc.read(buf)
                        if not chunk:
                            break
                        fdst.write(chunk)
                        copied += len(chunk)
                        now = time.monotonic()
                        if now - last_t >= 0.5:
                            el = max(0.1, now - self.manage_op_start_time_current_iso)
                            speed = copied / el if el > 0 else 0
                            eta_s = (
                                (self.manage_op_total_bytes_current_iso - copied)
                                / speed
                                if speed > 0
                                else float("inf")
                            )
                            self.root.after(
                                0,
                                self._update_progress_and_eta,
                                bar,
                                None,
                                spd,
                                eta_curr,
                                None,
                                copied,
                                None,
                                None,
                                speed,
                                eta_s,
                                None,
                            )
                            last_t = now
                self.root.after(
                    0,
                    self._update_progress_and_eta,
                    bar,
                    None,
                    spd,
                    eta_curr,
                    None,
                    self.manage_op_total_bytes_current_iso,
                    None,
                    None,
                    None,
                    0,
                    None,
                )
                self.log_message(f"ISO {iso_name} copiado.")
            elif action == "remove":
                path_to_rm = os.path.join(isos_dir, target_param)
                if os.path.exists(path_to_rm):
                    os.remove(path_to_rm)
                    self.log_message(f"ISO {target_param} eliminado.")
                else:
                    self.log_message(f"Advertencia: {target_param} no encontrado.")

            self.log_message("Actualizando grub.cfg...")
            current_isos = [
                f for f in os.listdir(isos_dir) if f.lower().endswith(".iso")
            ]
            if current_isos:
                with open(grub_cfg, "w") as f:
                    f.write(self.generate_grub_cfg_content(current_isos))
                self.log_message("grub.cfg actualizado.")
            else:
                with open(grub_cfg, "w") as f:
                    f.write(
                        "set timeout=5\nmenuentry 'No hay ISOs' {echo 'Añade ISOs a /isos/'; sleep 10}\n"
                    )
                self.log_message("Directorio ISOs vacío; grub.cfg con mensaje.")
            ok = True
            final_msg = (
                f"ISO {os.path.basename(str(target_param))} {verb} y GRUB actualizado."
            )
        except Exception as e:
            self.log_message(
                f"Error gestionando ISO ({action} {os.path.basename(str(target_param))}): {e}"
            )
            if "Cancelled by user" not in str(e):
                messagebox.showerror("Error Gestión", f"{e}")
            final_msg = (
                f"Operación '{action}' fallida."
                if "Cancelled" not in str(e)
                else "Operación cancelada."
            )
        finally:
            if os.path.ismount(TEMP_MOUNT_POINT):
                self.run_command(
                    ["umount", TEMP_MOUNT_POINT], check=False, log_cmd=False
                )
            self.root.after(0, self.verify_and_load_isos_from_usb)
            self.root.after(
                0,
                self._update_progress_and_eta,
                bar,
                lbl,
                spd,
                eta_curr,
                None,
                0,
                100,
                final_msg,
                None,
                None,
                None,
            )


if __name__ == "__main__":
    main_window = tk.Tk()
    app = MultibootUSBApp(main_window)
    main_window.mainloop()
