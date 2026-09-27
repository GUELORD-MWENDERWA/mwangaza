// Photo de l'élève réduite dans le navigateur avant l'envoi (le serveur n'a pas Pillow) : au plus
// 800 px de côté, en JPEG, quelques centaines de Ko au lieu des Mo d'un téléphone. Navigateur sans
// `createImageBitmap` (ou image illisible) : fichier d'origine, le serveur le vérifie.
const MAX_SIDE = 800;

export async function shrinkPhoto(file: File): Promise<File> {
  if (typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.85),
    );
    return blob ? new File([blob], "photo.jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file;
  }
}
