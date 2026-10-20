// Shared by CDK and the trusted preview management helper; no npm dependencies.
function previewStackName(branch) {
  if (typeof branch !== "string") throw new Error("preview branch is required");
  const normalized = branch.replace(/[^A-Za-z0-9]/gu, "-").toLowerCase()
    .replace(/^-+|-+$/g, "").slice(0, 30).replace(/-+$/g, "");
  if (!normalized) throw new Error("preview branch normalizes to an empty name");
  if (["development", "staging", "production"].includes(normalized)) {
    throw new Error("preview stack conflicts with a shared environment");
  }
  return `app-${normalized}`;
}

module.exports = { previewStackName };

if (require.main === module) {
  try {
    console.log(previewStackName(process.argv[2]));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
