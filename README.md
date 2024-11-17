# SC3020 - Project 2

## Initial Setup to run the Program

### Step 1: Check if `npm` and `node.js` has been installed on the machine
Ensure that your machine have installed `npm` or `node.js`, to test that run the following commands in your **PowerShell**:

*Note:* **PowerShell** stated here is **NOT** equivalent with **Command Prompt** so please use what is stated accordingly to the instruction.

```bash
node -v
npm -v
```

If it return:
```bash
node : The term 'node' is not recognized as the name of a cmdlet, function, script file, or operable program. Check
the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ node -v
+ ~~~~
    + CategoryInfo          : ObjectNotFound: (node:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```
and 
```
npm : The term 'npm' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the
spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ npm -v
+ ~~~
    + CategoryInfo          : ObjectNotFound: (npm:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```

That means you have not downloaded the packages yet. And you have to follow **Step 2** to setup your `npm` and `node.js`.

If the executed commands run without any error and they return the versions of your installations then no action is needed (You can ignore **Step 2**).


### Step 2: Install `npm` and `node.js`
Here is how you can setup `node.js` and `npm`:

Paste this line into your **PowerShell**:
```
winget install Schniz.fnm
```

When you are asked:
```
Do you agree to all the source agreements terms?
[Y] Yes  [N] No:
```

Type `y` in the answer and press **Enter**

Paste the following commands in your **PowerShell**
```
fnm env --use-on-cd | Out-String | Invoke-Expression
fnm use --install-if-missing 22
node -v 
npm -v 
```

If this error pop up after running `npm -v`:

```
npm : File C:\Users\tuann\AppData\Local\fnm_multishells\4028_1731641473437\npm.ps1 cannot be loaded because running
scripts is disabled on this system. For more information, see about_Execution_Policies at
https:/go.microsoft.com/fwlink/?LinkID=135170.
At line:1 char:1
+ npm -v
+ ~~~
    + CategoryInfo          : SecurityError: (:) [], PSSecurityException
    + FullyQualifiedErrorId : UnauthorizedAccess
```

Please re-run the **PowerShell** as **Administrator** and paste the following command in your **PowerShell**:

```
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser
```

Then you will be asked:
```
Execution Policy Change
The execution policy helps protect you from scripts that you do not trust. Changing the execution policy might expose
you to the security risks described in the about_Execution_Policies help topic at
https:/go.microsoft.com/fwlink/?LinkID=135170. Do you want to change the execution policy?
[Y] Yes  [A] Yes to All  [N] No  [L] No to All  [S] Suspend  [?] Help (default is "N"):
```

Please type `Y` in your answer and press **Enter**.


### Step 3: Ensure `node.js` and `npm` run properly every time you open PowerShell

In your **PowerShell**, type:
```
echo $profile
```

The example output could be:
```
C:\Users\_____\OneDrive\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1
```

Navigate to that file:

*Note:* If the file does not exist, please create the folders and files that replicate the output value:<br>
e.g. Let's say your folder just end at `C:\Users\_____\OneDrive\Documents\`<br>
You can create a new folder called `WindowsPowerShell` in it and create a file `Microsoft.PowerShell_profile.ps1` in `WindowsPowerShell` folder.

Open the `Microsoft.PowerShell_profile.ps1` with notepad and add the following line at the end of the file.
```
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
```

**Close** and **Re-open** the **PowerShell** then type:
```
node -v
npm -v
```

If they run properly and return the version installed then you are good to go.

#### Step 4: Install required `node.js` packages for the program to run properly

In **PowerShell** change the directory to our project folder using `cd` command.

Then
```
cd sql-visualizer
```

If the following prompt appear:
```
Can't find an installed Node version matching v20.9.0.
Do you want to install it? answer [y/N]:
```

Type `y` and press **Enter**

Then type:

```
npm install -g yarn
```
```
npm install
```
```
yarn install
```

### Step 4: Install the required library for Python

Navigate to this project folder through `cd` in your **Command Prompt** type:
```
pip install -r requirements.txt
```

### Step 5: Set PYTHONPATH

Set the `PYTHONPATH` environmental variable to your project folder (which is the parent directory of your `src` folder)
```
set PYTHONPATH="PATH/TO/PROJECT"
```
One example could be like this:
e.g.
```
set PYTHONPATH="C:\Users\_______\OneDrive\Desktop\SC3020\Project 2 Speed Run Everyone\SC3020-Project-2"
```

### Step 6: Run the Server

Now, ensure that your current working directory is the parent folder of the `src` folder. Next, Run the server using either `python -m` or `python3 -m`:
```
python -m src.project
```

You should see something like this:
```
/usr/local/bin/python3.10 /Users/mouse/Documents/GitHub/SC3020/SC3020-Project-2/src/project.py 
 * Serving Flask app 'project'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 338-494-232

> mantine-next-template@1.0.0 dev
> next dev


> mantine-next-template@1.0.0 dev
> next dev
 ▲ Next.js 14.0.1
   - Local:        http://localhost:3000

 ✓ Ready in 1491ms
 ✓ Ready in 1378ms
 ○ Compiling /page ...
 ✓ Compiled /page in 936ms (1739 modules)
```

# Note:
If for whatever reason your port 3000 is occupied, make sure to free it up. For example, you may see the following:
```
⚠ Port 3000 is in use, trying 3001 instead.
```

- If you see the above warning, try to access the web with `http://localhost:3001` or `http://localhost:3000` first, and try to select the database to connect.
- If **NO database is found** try to modify the code as follows:
set the port in the `__init__()` function of `DatabaseServer` in `project.py` to the **port mentioned** in the above line:

eg.:
```
class DatabaseServer:
    """Main server class handling database operations and API endpoints"""

    def __init__(self):
        self.app = Flask(__name__)
        self.app.json = SetEncoder(self.app)
        CORS(self.app, resources={
                    r"/api/*": {
                        "origins": ["http://localhost:3000", "http://localhost:3001"],  # ADD YOUR WARNING PORT HERE
                        "methods": ["GET", "POST", "OPTIONS"],
                        "allow_headers": ["Content-Type"]
                    }
                })
```

### Step 7: Need to wait when select database
You need to wait a while when you select the database until the sucessful message pop up on your screen, **DO NOT** spam click the database.








