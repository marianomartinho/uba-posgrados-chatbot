# 🚀 Deploy en Railway - Guía Paso a Paso

## ⏱️ Tiempo total: 10 minutos

---

## 📋 PASO 1: Crear Cuenta GitHub (2 min)

Si ya tenés cuenta GitHub, **saltá al Paso 2**.

1. Andá a: https://github.com/signup
2. Ingresá tu email
3. Creá contraseña
4. Elegí username
5. Verificá email
6. ✅ Listo

---

## 📁 PASO 2: Crear Repositorio y Subir Código (3 min)

### 2.1 Crear repositorio nuevo

1. Una vez logueado en GitHub, click en el **+** arriba a la derecha
2. Click en **"New repository"**
3. Completar:
   - **Repository name:** `uba-posgrados-chatbot`
   - **Description:** `Chatbot IA para posgrados UBA Derecho`
   - Dejar en **Public**
   - ✅ Marcar **"Add a README file"**
4. Click **"Create repository"**

### 2.2 Subir archivos

Ahora vas a ver tu repositorio vacío. Vamos a subir los 4 archivos:

1. Click en **"Add file"** → **"Upload files"**

2. **Arrastrá o seleccioná estos 4 archivos:**
   - `main.py` (copiar del artifact)
   - `requirements.txt` (copiar del artifact)
   - `railway.json` (copiar del artifact)
   - `README.md` (este archivo)

3. Abajo, en **"Commit changes"**:
   - Escribí: `Initial commit`
   - Click **"Commit changes"**

4. ✅ Archivos subidos correctamente

**💡 TIP:** Abrí cada archivo que te di en los artifacts, copiá el contenido, creá un archivo nuevo en tu compu con el mismo nombre, pegá el contenido y guardalo. Después arrastralos todos juntos a GitHub.

---

## 🚂 PASO 3: Crear Cuenta Railway (2 min)

1. Andá a: https://railway.app/

2. Click **"Login"**

3. Click **"Login with GitHub"**

4. Autorizá Railway a acceder a tu cuenta GitHub

5. ✅ Ya estás dentro de Railway

---

## 🎯 PASO 4: Deploy en 1 Click (2 min)

### 4.1 Crear nuevo proyecto

1. En Railway, click **"+ New Project"**

2. Seleccioná **"Deploy from GitHub repo"**

3. Buscá y seleccioná: **`uba-posgrados-chatbot`**

4. Click **"Deploy Now"**

Railway va a:
- ✅ Detectar que es Python
- ✅ Instalar dependencias
- ✅ Iniciar el servidor
- ⏳ Esperar 2-3 minutos...

### 4.2 Ver el deploy

Vas a ver una pantalla con logs. Cuando veas:

```
✅ Build successful
✅ Deployment successful
```

**¡Ya está funcionando!** Pero falta configurar la API Key...

---

## 🔑 PASO 5: Configurar OpenAI API Key (1 min)

### 5.1 Conseguir tu API Key (si no la tenés)

1. Andá a: https://platform.openai.com/api-keys
2. Click **"Create new secret key"**
3. Copiá la key (empieza con `sk-proj-` o `sk-`)
4. **¡GUARDALA!** No la vas a poder ver de nuevo

### 5.2 Agregar variable en Railway

1. En Railway, en tu proyecto, click en la tab **"Variables"**

2. Click **"+ New Variable"**

3. Completá:
   - **Variable name:** `OPENAI_API_KEY`
   - **Value:** [pegá tu API key acá]

4. Click **"Add"**

5. Railway va a **auto-redeploy** (1 min)

6. ✅ Listo, ahora sí funciona con IA!

---

## 🌐 PASO 6: Obtener Link Público (30 seg)

1. En Railway, click en la tab **"Settings"**

2. Buscá la sección **"Domains"**

3. Click **"Generate Domain"**

4. Railway te va a dar un link tipo:
   ```
   https://uba-posgrados-chatbot-production.up.railway.app
   ```

5. **¡ESTE ES TU LINK FINAL!** Copialo.

6. Abrilo en el navegador → **FUNCIONA** ✅

---

## 🎉 ¡LISTO! Compartir con tu Esposa

**Enviále el link:** https://tu-proyecto.up.railway.app

Ella puede:
- ✅ Usarlo desde cualquier dispositivo
- ✅ 24/7 sin interrupción
- ✅ Sin instalar nada
- ✅ Respuestas instantáneas

---

## 💰 Costos

- **GitHub:** GRATIS
- **Railway:** 
  - Trial: $5 crédito gratis
  - Luego: ~$5/mes
  - Primer mes prácticamente gratis con el trial

---

## 🔧 Mantenimiento

### ¿Tengo que hacer algo?

**NO.** Una vez deployado:

- ✅ Se mantiene solo
- ✅ Auto-actualiza el scraping cada 24hs
- ✅ Railway hace auto-restart si falla
- ✅ SSL/HTTPS automático

### Si querés actualizar el código

1. Editá el archivo en GitHub
2. Commit changes
3. Railway **auto-deploya** en 1 minuto

---

## 📊 Monitoring (Opcional)

Para ver si todo funciona:

1. Andá a tu link: `/health`
   ```
   https://tu-proyecto.up.railway.app/health
   ```

2. Vas a ver algo como:
   ```json
   {
     "status": "healthy",
     "cache_size": 28543,
     "cache_age": "2h 15m",
     "openai_configured": true
   }
   ```

---

## ❓ Problemas Comunes

### "Build Failed"
- Verificá que subiste los 4 archivos correctamente
- Reiniciá el deploy: click en los 3 puntitos → "Restart"

### "No responde el chatbot"
- Verificá que configuraste `OPENAI_API_KEY`
- Andá a `/health` para ver el status
- Revisá que tengas crédito en OpenAI

### "Página no carga"
- Esperá 1-2 minutos después del deploy
- Refrescá la página
- Probá en incógnito

---

## 🆘 Ayuda

Si tenés problemas:

1. **Railway Logs:** En tu proyecto → Tab "Deployments" → Click en el último deploy → Ver logs
2. **Health Check:** Andá a `/health` en tu URL
3. **Railway Discord:** https://discord.gg/railway (responden rápido)

---

## 🎯 Próximos Pasos (Opcional)

Si querés mejorarlo en el futuro:

- [ ] Conectar dominio custom (ej: `posgrados-uba.com`)
- [ ] Agregar analytics para ver qué preguntan más
- [ ] Expandir scraping a más páginas UBA
- [ ] Agregar sistema de feedback (👍👎)

---

**¿Dudas?** Todo debería funcionar siguiendo estos pasos al pie de la letra.