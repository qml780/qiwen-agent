import { describe, expect, it } from "vitest";
import { groupStatus, type Project } from "./domain";

const project = { current_stage: "music_drafting" } as Project;

describe("groupStatus", () => {
  it("marks earlier stages complete", () => {
    expect(groupStatus(project, ["concept_drafting", "concept_review"])).toBe("complete");
  });

  it("marks current group active", () => {
    expect(groupStatus(project, ["music_drafting", "music_review"])).toBe("active");
  });

  it("marks future groups pending", () => {
    expect(groupStatus(project, ["logic_drafting", "logic_review"])).toBe("pending");
  });
});
