/**
 * Client-side image compression utility.
 * Compresses large camera photos (e.g. 5MB-15MB) into high-quality JPEG (~300KB-600KB)
 * directly in the browser before upload, preserving sharp text and details.
 */
export async function compressImageFile(file, { maxWidth = 1920, maxHeight = 1920, quality = 0.82 } = {}) {
  if (!file || !(file instanceof File) || !file.type.startsWith('image/')) {
    // Non-image files (e.g. PDF) are returned untouched
    return file;
  }

  // Skip SVG and GIF animations, or very small images already under 300KB
  if (file.type === 'image/svg+xml' || file.type === 'image/gif' || file.size <= 300 * 1024) {
    return file;
  }

  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onerror = () => resolve(file);
    reader.onload = (e) => {
      const img = new Image();
      img.onerror = () => resolve(file);
      img.onload = () => {
        try {
          let { width, height } = img;

          // Scale proportionally to fit within maxWidth / maxHeight
          if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width = Math.round(width * ratio);
            height = Math.round(height * ratio);
          }

          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;

          const ctx = canvas.getContext('2d');
          if (!ctx) {
            resolve(file);
            return;
          }

          // Smooth rendering
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';

          // White background in case of transparent PNG converted to JPEG
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, width, height);
          ctx.drawImage(img, 0, 0, width, height);

          canvas.toBlob(
            (blob) => {
              if (!blob || blob.size >= file.size) {
                // If compression didn't reduce file size, keep original
                resolve(file);
                return;
              }

              // Keep original name, change extension to .jpg if needed
              const originalName = file.name.replace(/\.[^/.]+$/, '');
              const newFileName = `${originalName}.jpg`;
              const compressedFile = new File([blob], newFileName, {
                type: 'image/jpeg',
                lastModified: Date.now(),
              });
              resolve(compressedFile);
            },
            'image/jpeg',
            quality,
          );
        } catch {
          resolve(file);
        }
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}
