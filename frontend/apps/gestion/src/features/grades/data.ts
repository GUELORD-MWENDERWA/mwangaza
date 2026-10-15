// Notes (8.2.1), lues avec `grades.enter` ou `grades.enter_any` : ce que le compte peut noter, et
// la feuille d'un cours dans une période ou des examens.
import { api, call, type Schemas } from "@mwangaza/api";
import { useQuery } from "@tanstack/react-query";

import { keys } from "../../lib/queries";

export type Grading = Schemas["Grading"];
export type GradingClass = Schemas["GradingClass"];
export type GradingCourse = Schemas["GradingCourse"];
export type Sheet = Schemas["Sheet"];

export function useGrading() {
  return useQuery({ queryKey: keys.grading, queryFn: () => call(api.GET("/api/grading/")) });
}

export function useSheet(courseId: string, termId: string) {
  return useQuery({
    queryKey: [...keys.gradeSheet, courseId, termId],
    queryFn: () =>
      call(
        api.GET("/api/courses/{id}/terms/{term}/grades/", {
          params: { path: { id: courseId, term: termId } },
        }),
      ),
    enabled: Boolean(courseId && termId),
  });
}
