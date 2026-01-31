import { useEffect, useMemo, useState } from "react";

type ReviewItem = {
  label: string;
  value: string;
  reason: string;
};

const MOCK_REVIEW_ITEMS: ReviewItem[] = [
  {
    label: "Client Name",
    value: "Jane Doe",
    reason: "From client profile",
  },
  {
    label: "Risk Disclosure",
    value: "Investing involves risk, including possible loss of principal.",
    reason: "Standard SEC disclosure",
  },
  {
    label: "Suitability Summary",
    value:
      "Client has moderate risk tolerance and long-term growth objective, making ETF-based growth strategy appropriate.",
    reason: "Generated from advisor notes + profile",
  },
];

export default function WorkspacePage() {
  const [docText, setDocText] = useState<string>("");
  const [meetingFile, setMeetingFile] = useState<File | null>(null);
  const [profileFile, setProfileFile] = useState<File | null>(null);
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>(MOCK_REVIEW_ITEMS);
  const [isLoading, setIsLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editedValue, setEditedValue] = useState<string>(reviewItems[0]?.value ?? "");
  const [savedByIndex, setSavedByIndex] = useState<Record<number, string>>({});
  const [savedDocTextByIndex, setSavedDocTextByIndex] = useState<Record<number, string>>({});

  const styles = useMemo(
    () => ({
      page: {
        minHeight: "100vh",
        background: "#f6f7fb",
        color: "#081D4D",
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial",
      } as const,
      container: {
        maxWidth: 1200,
        margin: "0 auto",
        padding: "24px 24px 40px",
      } as const,
      header: {
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 16,
        padding: "14px 18px",
        borderRadius: 14,
        background: "white",
        border: "1px solid #e5e7eb",
        boxShadow: "0 8px 22px rgba(0,0,0,0.06)",
      } as const,
      titleWrap: {
        display: "flex",
        flexDirection: "column",
        gap: 4,
      } as const,
      title: {
        margin: 0,
        fontSize: 22,
        fontWeight: 800,
        letterSpacing: -0.2,
      } as const,
      subtitle: {
        margin: 0,
        fontSize: 13,
        color: "#6b7280",
      } as const,
      statusPill: {
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 10px",
        borderRadius: 999,
        border: "1px solid #e5e7eb",
        background: "#f9fafb",
        fontSize: 12,
        color: "#081D4D",
        whiteSpace: "nowrap",
      } as const,
      stepControls: {
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
      } as const,
      stepBtn: {
        border: "1px solid #e5e7eb",
        background: "white",
        color: "#081D4D",
        borderRadius: 10,
        padding: "6px 10px",
        fontSize: 12,
        fontWeight: 700,
        cursor: "pointer",
      } as const,
      stepBtnDisabled: {
        opacity: 0.5,
        cursor: "not-allowed",
      } as const,
      grid: {
        marginTop: 18,
        display: "grid",
        gridTemplateColumns: "1fr 360px",
        gap: 16,
        alignItems: "start",
      } as const,
      sideColumn: {
        display: "flex",
        flexDirection: "column",
        gap: 16,
      } as const,
      card: {
        background: "white",
        border: "1px solid #e5e7eb",
        borderRadius: 14,
        boxShadow: "0 8px 22px rgba(0,0,0,0.06)",
        overflow: "hidden",
      } as const,
      cardHeader: {
        padding: "12px 14px",
        borderBottom: "1px solid #eef2f7",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
      } as const,
      cardTitle: {
        margin: 0,
        fontSize: 13,
        fontWeight: 800,
        color: "#081D4D",
        textTransform: "uppercase",
        letterSpacing: 0.6,
      } as const,
      uploadRow: {
        display: "flex",
        alignItems: "center",
        gap: 10,
      } as const,
      input: {
        fontSize: 13,
      } as const,
      viewer: {
        height: 640,
        background: "#fafafa",
      } as const,
      viewerBody: {
        height: "100%",
      } as const,
      docEditor: {
        width: "100%",
        height: "100%",
        border: "none",
        padding: 16,
        resize: "none",
        fontSize: 13,
        lineHeight: 1.4,
        color: "#081D4D",
        background: "transparent",
        fontFamily: "inherit",
      } as const,
      viewerEmpty: {
        padding: 18,
        color: "#6b7280",
        fontSize: 13,
      } as const,
      reviewBody: {
        padding: 14,
      } as const,
      stepText: {
        fontSize: 12,
        color: "#6b7280",
      } as const,
      fieldLabel: {
        margin: "10px 0 0",
        fontSize: 16,
        fontWeight: 800,
      } as const,
      reason: {
        margin: "6px 0 0",
        fontSize: 12,
        color: "#6b7280",
      } as const,
      valueBox: {
        marginTop: 10,
        padding: 12,
        border: "1px solid #eef2f7",
        borderRadius: 12,
        background: "#fbfdff",
        fontSize: 13,
        lineHeight: 1.35,
      } as const,
      btnRow: {
        display: "flex",
        gap: 10,
        marginTop: 14,
      } as const,
      btn: {
        flex: 1,
        padding: "10px 12px",
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        background: "white",
        fontWeight: 700,
        cursor: "pointer",
      } as const,
      btnPrimary: {
        background: "#081D4D",
        color: "white",
        border: "1px solid #081D4D",
      } as const,
      footerHint: {
        marginTop: 12,
        fontSize: 12,
        color: "#6b7280",
      } as const,
    }),
    []
  );

  const currentItem = reviewItems[currentIndex];
  const isDone = currentIndex >= reviewItems.length;
  const hasBothUploads = Boolean(meetingFile && profileFile);
  const hasUpload = hasBothUploads;
  const isSavedForCurrent =
    !isDone &&
    savedDocTextByIndex[currentIndex] !== undefined &&
    savedDocTextByIndex[currentIndex] === docText;

  useEffect(() => {
    if (!currentItem) return;
    const saved = savedByIndex[currentIndex];
    setEditedValue(saved !== undefined ? saved : currentItem.value);
  }, [currentIndex, savedByIndex, currentItem]);

  async function handleUpload(
    e: React.ChangeEvent<HTMLInputElement>,
    source: "meeting" | "profile"
  ) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (source === "meeting") {
      setMeetingFile(file);
    } else {
      setProfileFile(file);
    }

    setDocText("");
    setSavedDocTextByIndex({});
  }

  useEffect(() => {
    if (!meetingFile || !profileFile) return;

    const runAutofill = async () => {
      setIsLoading(true);
      setErrorText(null);

      try {
        const formData = new FormData();
        formData.append("client_pdf", profileFile);
        formData.append("notes_pdf", meetingFile);
        formData.append("form_type", "Reg BI suitability summary");
        formData.append("use_policy_docs", "true");
        formData.append("top_k_docs", "3");

        const resp = await fetch("http://127.0.0.1:8000/autofill_two_pdfs", {
          method: "POST",
          body: formData,
        });

        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(text || "Autofill request failed");
        }

        const data = await resp.json();
        setDocText(typeof data?.document_text === "string" ? data.document_text : "");
        const fields = data?.autofilled_fields ?? {};
        const explanations = data?.explanations ?? {};

        const nextItems: ReviewItem[] = Object.entries(fields).map(([key, value]) => ({
          label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
          value: value === null || value === undefined ? "" : String(value),
          reason: explanations[key] || "Generated by AI",
        }));

        setReviewItems(nextItems.length ? nextItems : MOCK_REVIEW_ITEMS);
        setCurrentIndex(0);
        setSavedByIndex({});
      setEditedValue(nextItems[0]?.value ?? "");
      setSavedDocTextByIndex({});
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Autofill request failed");
      setReviewItems(MOCK_REVIEW_ITEMS);
      } finally {
        setIsLoading(false);
      }
    };

    runAutofill();
  }, [meetingFile, profileFile]);

  function handleClear() {
    setEditedValue("");
  }

  function handleSave() {
    if (isDone) return;
    setSavedByIndex((prev) => ({ ...prev, [currentIndex]: editedValue }));
    setSavedDocTextByIndex((prev) => ({ ...prev, [currentIndex]: docText }));
  }

  function handleBackStep() {
    setCurrentIndex((i) => Math.max(0, i - 1));
  }

  function handleNextStep() {
    // Don’t allow moving forward until current step is saved
    if (!isSavedForCurrent) return;
    setCurrentIndex((i) => Math.min(reviewItems.length, i + 1));
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <div style={styles.header}>
          <div style={styles.titleWrap}>
            <h1 style={styles.title}>Compliance Autofill Review</h1>
            <p style={styles.subtitle}>
              Upload both PDFs, edit the suggestion, then click Save to enable Next.
            </p>
          </div>

          <div style={styles.statusPill}>
            <div style={styles.stepControls}>
              <button
                type="button"
                onClick={handleBackStep}
                disabled={currentIndex === 0}
                style={{
                  ...styles.stepBtn,
                  ...(currentIndex === 0 ? styles.stepBtnDisabled : {}),
                }}
              >
                Back
              </button>

              <span>
                {!isDone
                  ? `Step ${currentIndex + 1} / ${reviewItems.length}`
                  : "Complete"}
              </span>

              <button
                type="button"
                onClick={handleNextStep}
                disabled={isDone || !isSavedForCurrent}
                style={{
                  ...styles.stepBtn,
                  ...((isDone || !isSavedForCurrent) ? styles.stepBtnDisabled : {}),
                }}
              >
                Next
              </button>
            </div>
          </div>
        </div>

        <div style={styles.grid}>
          {/* Document Viewer */}
          <div style={{ ...styles.card, ...styles.viewer }}>
            <div style={styles.cardHeader}>
              <p style={styles.cardTitle}>Document</p>
            </div>

            <div style={styles.viewerBody}>
              {!hasBothUploads ? (
                <div style={styles.viewerEmpty}>
                  Upload both Meeting Notes and Client Profile to preview the document.
                </div>
              ) : (
                <textarea
                  style={styles.docEditor}
                  value={docText}
                  onChange={(e) => setDocText(e.target.value)}
                  placeholder={isLoading ? "Generating document text..." : "Document text will appear here."}
                  disabled={isLoading}
                />
              )}
            </div>
          </div>

          <div style={styles.sideColumn}>
            {/* Review Panel */}
            {hasUpload ? (
              <div style={styles.card}>
                <div style={styles.cardHeader}>
                  <p style={styles.cardTitle}>Review</p>
                  <span style={styles.stepText}>
                    {isDone ? "0 remaining" : `${reviewItems.length - currentIndex} remaining`}
                  </span>
                </div>

                <div style={styles.reviewBody}>
                  {isLoading ? (
                    <>
                      <h3 style={styles.fieldLabel}>Generating…</h3>
                      <p style={styles.reason}>Extracting the PDF and running autofill.</p>
                    </>
                  ) : errorText ? (
                    <>
                      <h3 style={styles.fieldLabel}>Autofill Failed</h3>
                      <p style={styles.reason}>{errorText}</p>
                    </>
                  ) : !isDone ? (
                    <>
                      <div style={styles.stepText}>
                        Review {currentIndex + 1} of {reviewItems.length}
                      </div>

                      <h3 style={styles.fieldLabel}>{currentItem.label}</h3>
                      <p style={styles.reason}>Reason: {currentItem.reason}</p>

                      <textarea
                        style={{ ...styles.valueBox, width: "100%", minHeight: 90, resize: "vertical" }}
                        value={editedValue}
                        onChange={(e) => setEditedValue(e.target.value)}
                      />

                      <div style={styles.btnRow}>
                        <button onClick={handleClear} style={styles.btn}>
                          Clear
                        </button>
                        <button
                          onClick={isSavedForCurrent ? handleNextStep : handleSave}
                          style={{ ...styles.btn, ...styles.btnPrimary }}
                          disabled={isDone}
                          title={isSavedForCurrent ? "Go to next step" : "Save this field to enable Next"}
                        >
                          {isSavedForCurrent ? "Next" : "Save"}
                        </button>
                      </div>

                      <div style={styles.footerHint}>
                        Tip: Save each step to unlock Next. Upload both PDFs to run autofill.
                      </div>
                    </>
                  ) : (
                    <>
                      <h3 style={styles.fieldLabel}>Review Complete 🎉</h3>
                      <p style={styles.reason}>All fields have been reviewed.</p>
                    </>
                  )}
                </div>
              </div>
            ) : null}

            {/* Upload Card */}
            <div style={styles.card}>
              <div style={styles.cardHeader}>
                <p style={styles.cardTitle}>Upload</p>
              </div>
              <div style={styles.reviewBody}>
                <div style={{ ...styles.uploadRow, flexDirection: "column", alignItems: "flex-start", gap: 12 }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <span style={styles.stepText}>Meeting Notes</span>
                    <input
                      style={styles.input}
                      type="file"
                      accept="application/pdf"
                      onChange={(e) => handleUpload(e, "meeting")}
                    />
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <span style={styles.stepText}>Client Profile</span>
                    <input
                      style={styles.input}
                      type="file"
                      accept="application/pdf"
                      onChange={(e) => handleUpload(e, "profile")}
                    />
                  </label>
                </div>
                <p style={styles.reason}>Upload both PDFs to run autofill and populate the review.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
