
# install nvm
if which nvm > /dev/null; then
  echo "nvm                       is already installed"
else
  export NVM_DIR="$HOME/.nvm" && (
    git clone https://github.com/creationix/nvm.git "$NVM_DIR"
    cd "$NVM_DIR"
    git checkout `git describe --abbrev=0 --tags --match "v[0-9]*" origin`
  ) && . "$NVM_DIR/nvm.sh"
fi
if which npm > /dev/null; then
  echo "npm                       is already installed"
else
  echo "npm is not installed, installing through brew"
  nvm install 0.10
fi

# install gleemail
if ls node_modules/gleemail/bin/gleemail > /dev/null; then
  echo "gleemail                  is already installed"
  echo ""
  echo "Type node_modules/gleemail/bin/gleemail to execute gleemail"
else
  echo "gleemail is not installed, installing with npm"
  npm install gleemail
fi
