pipeline {
  agent any

  parameters {
    string(name: 'VM_HOST', defaultValue: '20.193.69.220', description: 'Azure VM public IP')
    string(name: 'VM_USER', defaultValue: 'azureuser', description: 'SSH user on VM')
    string(name: 'BACKEND_URL', defaultValue: 'http://20.193.69.220:8081', description: 'Public API URL (installer bake + smoke)')
    booleanParam(name: 'SKIP_INSTALLER', defaultValue: false, description: 'Skip Windows connector EXE build/upload')
    booleanParam(name: 'SKIP_CI', defaultValue: false, description: 'Skip CI build/test stages')
    booleanParam(name: 'USE_GPU', defaultValue: false, description: 'Include docker-compose.gpu.yml (requires NVIDIA on VM)')
  }

  environment {
    VM_APP_DIR = '/opt/onevo/app'
    ONEVO_PYTHON = 'C:\\Users\\Abdul Baasith\\AppData\\Local\\Python\\bin\\python.exe'
    ONEVO_ISCC = 'C:\\Users\\Abdul Baasith\\AppData\\Local\\Programs\\Inno Setup 6\\ISCC.exe'
  }

  stages {
    stage('CI') {
      when { expression { !params.SKIP_CI } }
      parallel {
        stage('Backend') {
          steps {
            dir('backend') {
              bat 'dotnet restore Onevo.Api.csproj'
              bat 'dotnet build Onevo.Api.csproj -c Release --no-restore'
            }
          }
        }
        stage('Dashboard') {
          steps {
            dir('dashboard') {
              bat 'npm ci'
              bat 'npm run build'
            }
          }
        }
        stage('Connector tests') {
          steps {
            dir('connector') {
              bat '"%ONEVO_PYTHON%" -m pip install -r requirements.txt pytest'
              bat 'set PYTHONPATH=.&& "%ONEVO_PYTHON%" -m pytest tests/ -q'
            }
          }
        }
      }
    }

    stage('Deploy to VM') {
      steps {
        script {
          def extra = ''
          if (params.SKIP_INSTALLER) { extra += ' -SkipInstaller' }
          if (params.USE_GPU) { extra += ' -UseGpu' }
          withCredentials([sshUserPrivateKey(
            credentialsId: 'onevo-vm-ssh-key',
            keyFileVariable: 'SSH_KEY',
            usernameVariable: 'SSH_USER'
          )]) {
            bat '''
              powershell -ExecutionPolicy Bypass -File scripts/deploy-vm.ps1 ^
                -VmHost ''' + params.VM_HOST + ''' ^
                -VmUser ''' + params.VM_USER + ''' ^
                -BackendUrl ''' + params.BACKEND_URL + ''' ^
                -PythonPath "%ONEVO_PYTHON%" ^
                -IsccPath "%ONEVO_ISCC%" ^
                -SshKeyPath "%SSH_KEY%"''' + extra + '''
            '''
          }
        }
      }
    }

    stage('Smoke test') {
      steps {
        bat """
          curl -sf ${params.BACKEND_URL}/api/health
          curl -sf -o NUL -w "Dashboard HTTP %%{http_code}\\n" http://${params.VM_HOST}:4200/
        """
      }
    }
  }

  post {
    success {
      echo "ONEVO deploy succeeded — dashboard http://${params.VM_HOST}:4200"
    }
    failure {
      echo 'Deploy failed — check Jenkins console and VM docker compose logs.'
    }
  }
}
