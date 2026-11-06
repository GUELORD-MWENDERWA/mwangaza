// Séance photo (lot 10, 6.1) : une classe ou le personnel dans l'ordre de la liste. Les photos sont
// envoyées une à une ; si le réseau tombe, elles attendent dans la file et partent au retour.
import { api, call } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { shrinkPhoto } from "../students/photo";

export type SessionKind = "students" | "staff";
export type Person = { id: string; name: string; detail: string; photo: string | null };

/** Tout le monde d'une classe (ou du personnel actif), page après page. */
export function useSessionPeople(kind: SessionKind, classGroup: string) {
  return useQuery({
    queryKey: ["cards", "session", kind, classGroup],
    enabled: kind === "staff" || Boolean(classGroup),
    staleTime: 0,
    queryFn: async (): Promise<Person[]> => {
      const people: Person[] = [];
      for (let page = 1; ; page++) {
        const query = { ...(page > 1 ? { page } : {}) };
        if (kind === "students") {
          const data = await call(
            api.GET("/api/attendance/cards/students/", {
              params: { query: { class_group: classGroup, ...query } },
            }),
          );
          for (const item of data.results)
            people.push({
              id: item.student,
              name: item.name,
              detail: item.matricule,
              photo: item.photo,
            });
          if (!data.next) return people;
        } else {
          const data = await call(api.GET("/api/attendance/cards/staff/", { params: { query } }));
          for (const item of data.results)
            people.push({
              id: item.member,
              name: item.name,
              detail: item.title || item.roles.join(", "),
              photo: item.photo,
            });
          if (!data.next) return people;
        }
      }
    },
  });
}

export function uploadSessionPhoto(kind: SessionKind, id: string, photo: File) {
  const body = new FormData();
  body.append("photo", photo);
  const options = { params: { path: { id } }, body: body as unknown as { photo: string } };
  return kind === "students"
    ? call(api.POST("/api/attendance/photos/students/{id}/", options))
    : call(api.POST("/api/attendance/photos/staff/{id}/", options));
}

/** Image de la caméra recadrée en 4:5 (600 × 750), JPEG. */
export async function frameToFile(video: HTMLVideoElement): Promise<File | null> {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) return null;
  const crop = Math.min(width, (height * 4) / 5);
  const cropHeight = (crop * 5) / 4;
  const canvas = document.createElement("canvas");
  canvas.width = 600;
  canvas.height = 750;
  canvas
    .getContext("2d")
    ?.drawImage(
      video,
      (width - crop) / 2,
      (height - cropHeight) / 2,
      crop,
      cropHeight,
      0,
      0,
      600,
      750,
    );
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.88),
  );
  return blob ? new File([blob], "photo.jpg", { type: "image/jpeg" }) : null;
}

export { shrinkPhoto };
