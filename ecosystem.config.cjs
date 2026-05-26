module.exports = {
  apps: [
    {
      name: 'spark-backend',
      script: 'venv/bin/python',
      args: '抖音自动续火花-后端.py',
      cwd: __dirname,
      interpreter: 'none',
      env: {
        HOST: '127.0.0.1',
        PORT: '9844',
        HEADLESS: 'true',
        ALLOW_PUBLIC_BIND: 'false',
        CORS_ORIGINS: 'https://spark.aprivity.xyz,http://localhost:5173,http://127.0.0.1:5173'
      }
    }
  ]
}
