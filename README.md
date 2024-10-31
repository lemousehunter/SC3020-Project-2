# SC3020-Project-2
QEP Visualizer

# Download the pg_hint_plan for Postgresql
## Installation of gcc and g++ compiler
   **For Windows:** <i>Reference: <a href = "https://code.visualstudio.com/docs/cpp/config-mingw">Using GCC with MinGW</a></i><br>
   
   a. Installing the MinGW-w64 toolchain <a href = "https://www.msys2.org/">here</a>.<br>
   
   b. In the wizard, choose your desired Installation Folder. Record this directory for later. In most cases, the recommended directory is acceptable. The same applies when you get to setting the start menu shortcuts step. When complete, ensure the <b>Run MSYS2</b> now box is checked and select <b>Finish</b>. This will open a MSYS2 terminal window for you.<br>
   
   c. In the `MSYS2 UCRT64 environment` <b>(not MinGW64 or MinGW32)</b> terminal paste this command to download the MinGW-w64 toolchain.<br>
   ```
   pacman -S --needed base-devel mingw-w64-ucrt-x86_64-toolchain
   ```
   
   d. Accept the default number of packages in the toolchain by pressing `Enter`.<br>
   ![image](https://github.com/user-attachments/assets/8d1a8d78-5f8d-4290-a129-c88317e98d64)

   e. Press `Y` when prompted to proceed with the installation.<br>
   
   f. Add the path of your MinGW-w64 `bin` folder to the Windows `PATH` environment variable by using the following steps:<br> 
   - f.1. In the Windows search bar, type <b>Settings</b> to open your Windows Settings.<br>
   
   - f.2. Search for <b>Edit environment variables for your account</b>.<br>
   
   - f.3. In your <b>User variables</b>, select the `Path` variable and then select <b>Edit</b>.<br>
   
   - f.4. Select <b>New</b> and add the MinGW-w64 destination folder you recorded during the installation process to the list. If you used the default settings above, then this will be the path: `C:\msys64\ucrt64\bin`.<br>
   
        f.5. Select <b>OK</b>, and then select <b>OK</b> again in the <b>Environment Variables</b> window to update the `PATH` environment variable. You have to reopen any console windows for the updated `PATH` environment variable to be available<br>

    g. To check if g++, GCC, gdb has been installed correctly, open a new <b>command prompt (CMD)</b> and paste in these lines
    ```bash
    gcc --version
    g++ --version
    gdb --version
    ```

## Installation of pg_hint_plan
  
- Go to [Download pg_hint_plan version PG14](https://github.com/ossc-db/pg_hint_plan/tree/PG14)
