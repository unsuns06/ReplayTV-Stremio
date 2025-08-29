# Hugging Face Space Deployment Guide for Stremio Addon

This guide will walk you through the process of deploying your Stremio addon to Hugging Face Spaces.

## 1. Fork the Repository

If you haven't already, fork the `ReplayTV-Stremio` repository on GitHub. You can find the repository here: [https://github.com/gemini-testing/ReplayTV-Stremio](https://github.com/gemini-testing/ReplayTV-Stremio)

## 2. Create a Hugging Face Space

1.  Sign up or log in to Hugging Face: [https://huggingface.co/](https://huggingface.co/)
2.  Create a new space: [https://huggingface.co/new-space](https://huggingface.co/new-space)
3.  Give your space a name.
4.  Choose `Docker` as the SDK.
5.  Select the `Blank` template.
6.  Choose `Public` visibility.
7.  Click on `Create space`.

## 3. Set Secrets

In the `Settings` tab of your Hugging Face Space, you need to add the following secrets:

*   `MEDIAFLOW_PROXY_URL`: The URL of your online mediaflow server.
*   `MEDIAFLOW_API_PASSWORD`: The password for your mediaflow server.

## 4. Add the Dockerfile

1.  Go to the `Files` tab of your Hugging Face Space.
2.  Click on `Add file` and select `Create a new file`.
3.  Name the file `Dockerfile`.
4.  Paste the following content into the file:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git

# Replace YourUsername/YourRepoName with your fork of the ReplayTV-Stremio repository
RUN git clone https://github.com/unsuns06/ReplayTV-Stremio.git .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

**Important:** Replace `https://github.com/unsuns06/ReplayTV-Stremio.git` with the URL of your forked repository.

5.  Click on `Commit new file` to save the changes.

## 5. Deploy and Get the URL

1.  Hugging Face Spaces will automatically build and deploy your space.
2.  You can monitor the build process in the `Logs` tab.
3.  Once the space is deployed successfully, you can find the public URL of your addon in the `Embed this space` option in the top right corner.

Your Stremio addon is now deployed and ready to be used!