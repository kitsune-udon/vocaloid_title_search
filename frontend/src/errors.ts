import { ApiError } from "./api";
type ErrorContext = "initial" | "search" | "detail" | "stats";

export function userFacingError(caught: unknown, context: ErrorContext): string {
  if (caught instanceof ApiError) {
    if (caught.status === null) {
      return "通信に失敗しました。ネットワーク状態を確認して再実行してください。";
    }
    if (caught.status === 400) {
      return context === "detail"
        ? "詳細ページのURLが不正です。"
        : "検索条件に不正な値があります。入力内容を確認してください。";
    }
    if (caught.status === 404) {
      return context === "detail"
        ? "詳細情報がDBにありません。DBを再構築してください。"
        : "対象のデータが見つかりませんでした。";
    }
    if (caught.status === 503 || caught.message === "database is not ready") {
      return "DBが未作成、未配置、または更新が必要です。先にDBを作成してください。";
    }
    if (caught.status >= 500) {
      return "サーバー側でエラーが発生しました。時間を置いて再実行してください。";
    }
  }
  const fallback = caught instanceof Error ? caught.message : "";
  if (context === "initial") return `初期データを取得できませんでした。${fallback}`.trim();
  if (context === "stats") return `統計情報を取得できませんでした。${fallback}`.trim();
  if (context === "detail") return "詳細取得に失敗しました。";
  return `検索に失敗しました。${fallback}`.trim();
}
