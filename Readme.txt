# (Español) Creador USB Multiboot para Linux / (English) Multiboot USB Creator for Linux

## Español

### Descripción
Este proyecto es una aplicación Python con interfaz gráfica (GUI) diseñada para crear unidades USB multiboot en sistemas Linux. Permite a los usuarios formatear una unidad USB, instalar GRUB2 (para arranque BIOS/MBR) y copiar múltiples archivos ISO, generando un menú de arranque para seleccionar qué ISO iniciar. También incluye funcionalidades para añadir o quitar ISOs de un USB multiboot previamente creado con esta herramienta.

### Características
- Creación de unidades USB multiboot desde cero.
- Interfaz gráfica intuitiva construida con Tkinter.
- Selección de dispositivo USB y archivos ISO a través de la GUI.
- Instalación automática de GRUB2 (para arranque BIOS/MBR).
- Generación de un archivo de configuración `grub.cfg` básico para arrancar ISOs comunes (especialmente útil para distribuciones basadas en Debian/Ubuntu y Fedora).
- Gestión de USBs multiboot existentes:
    - Añadir nuevos archivos ISO.
    - Quitar archivos ISO existentes.
- Barra de progreso para la copia de archivos ISO.
- Script de instalación de dependencias para distribuciones Linux comunes (`install_dependencies.sh`).

### Requisitos Previos
- Un sistema operativo Linux.
- Python 3.
- Tkinter para Python 3 (generalmente el paquete `python3-tk` o similar).
- Privilegios de superusuario (root/sudo) para ejecutar la aplicación y el script de instalación.
- Dependencias del sistema (instalables con el script `install_dependencies.sh`):
    - `grub2` (específicamente paquetes como `grub-pc`, `grub2-pc`, `grub-bios`, `grub-i386-pc` o `grub` dependiendo de la distribución, para el sector de arranque BIOS/MBR).
    - `parted` (para particionado de disco).
    - `dosfstools` (para `mkfs.fat`).
    - `util-linux` (para `lsblk`, `partprobe`, etc.).

### Instalación y Configuración
1.  Clona este repositorio (o descarga los archivos):
    ```bash
    git clone [https://github.com/danitxu79/MultiBoot.git](https://github.com/danitxu79/MultiBoot.git)
    cd MultiBoot
    ```


2.  Ejecuta el script de instalación de dependencias. Este script intentará detectar tu distribución e instalar los paquetes necesarios. Deberás ejecutarlo con `sudo`:
    ```bash
    chmod +x install_dependencies.sh
    sudo ./install_dependencies.sh
    ```
    Si el script no soporta tu distribución o encuentras problemas, por favor instala las dependencias listadas en la sección "Requisitos Previos" manualmente usando el gestor de paquetes de tu sistema.

### Uso
Para ejecutar la aplicación principal:
```bash
sudo python3 MultiBoot.py


English


Description

This project is a Python application with a graphical user interface (GUI) designed to create multiboot USB drives on Linux systems. It allows users to format a USB drive, install GRUB2 (for BIOS/MBR booting), and copy multiple ISO files, generating a boot menu to select which ISO to start. It also includes features to add or remove ISOs from a multiboot USB previously created with this tool.
Features

    Creation of multiboot USB drives from scratch.
    Intuitive graphical interface built with Tkinter.
    USB device and ISO file selection through the GUI.
    Automatic installation of GRUB2 (for BIOS/MBR booting).
    Generation of a basic grub.cfg configuration file to boot common ISOs (especially useful for Debian/Ubuntu and Fedora-based distributions).
    Management of existing multiboot USBs:
        Add new ISO files.
        Remove existing ISO files.
    Progress bar for ISO file copying.
    Dependency installation script (install_dependencies.sh) for common Linux distributions.

Prerequisites

    A Linux operating system.
    Python 3.
    Tkinter for Python 3 (usually the python3-tk package or similar).
    Superuser (root/sudo) privileges to run the application and the installation script.
    System dependencies (installable with the install_dependencies.sh script):
        grub2 (specifically packages like grub-pc, grub2-pc, grub-bios, grub-i386-pc, or grub depending on the distribution, for BIOS/MBR boot sector).
        parted (for disk partitioning).
        dosfstools (for mkfs.fat).
        util-linux (for lsblk, partprobe, etc.).

Installation and Setup

    Clone this repository (or download the files):
    Bash

git clone [https://github.com/danitxu79/MultiBoot.git](https://github.com/danitxu79/MultiBoot.git)
cd MultiBoot

Run the dependency installation script. This script will attempt to detect your distribution and install the necessary packages. You must run it with sudo:
Bash

    chmod +x install_dependencies.sh
    sudo ./install_dependencies.sh

    If the script does not support your distribution or you encounter issues, please install the dependencies listed in the "Prerequisites" section manually using your system's package manager.

Usage

To run the main application:
Bash

sudo python3 MultiBoot.py

(Replace multiboot_creator.py with the actual name of your Python file if different).

Important: The application must be run with sudo because it requires low-level access for operations such as formatting disks, mounting/unmounting partitions, and installing the GRUB bootloader.

Graphical Interface:

    USB Selection: At the top, select your USB device from the dropdown list. Refresh the list if necessary.
    "Create New Multiboot USB" Tab:
        Use "Add ISO" to select the .iso files you want to include on the new USB.
        Click "Create Multiboot USB!". You will be asked for final confirmation before formatting the selected disk.
    "Manage Existing USB" Tab:
        If the USB selected in the top dropdown is a compatible multiboot USB (usually created by this tool or with a similar structure: an /isos directory and /boot/grub/grub.cfg), the current ISOs it contains will be listed.
        You can use "Add New ISO to USB" to add more ISOs or "Remove Selected ISO from USB" to delete one.
        The progress bar will indicate file copying when adding an ISO.
    Operations Log: At the bottom, a text window displays the commands the application is running in the background and any error or status messages.

⚠️ Important Warnings

    RISK OF DATA LOSS: Creating a multiboot USB will completely format the selected USB device. Make absolutely sure you choose the correct device and have backed up any important data beforehand. Use this software at your own risk.
    Root Privileges: The application must be run with sudo.
    BIOS/MBR Boot: Currently, the tool is primarily designed to create USBs with BIOS boot and an MBR partition scheme. Full UEFI support may require GPT partitioning and an EFI GRUB setup, which is not robustly implemented.
    ISO Compatibility: The generated GRUB configuration is basic and looks for common patterns to boot ISOs (especially Linux Live distributions). However, some ISOs (such as Windows installers, or ISOs with very specific or proprietary boot methods) may not boot correctly without manual, detailed configuration of the grub.cfg file on the USB.
