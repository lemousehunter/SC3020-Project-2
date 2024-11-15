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

**Close** and **Re-open** the PowerShell then type:
```
node -v
npm -v
```

If they run properly and return the version installed then you are good to go.














