import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ApplicationStack, stackNameForEnvironment } from "../lib/application-stack";
import { previewStackName } from "../lib/preview-stack-name.cjs";

function lambdaAsset(lambdaAssetPath: string): { hash: string; files: string[] } {
  const outdir = mkdtempSync(join(tmpdir(), "ai-driven-development-cdk-"));
  try {
    const app = new cdk.App({ outdir });
    new ApplicationStack(app, "AssetTest", { environment: "development", lambdaAssetPath });
    app.synth();

    const assetDirectory = readdirSync(outdir, { withFileTypes: true }).find(
      (entry) => entry.isDirectory() && entry.name.startsWith("asset."),
    );
    if (!assetDirectory) {
      throw new Error("Lambda asset was not staged");
    }

    const directory = join(outdir, assetDirectory.name);
    return {
      hash: assetDirectory.name.slice("asset.".length),
      files: ["handler.py", "handler_test.py", "nested/handler_test.py"].filter((file) => existsSync(join(directory, file))),
    };
  } finally {
    rmSync(outdir, { recursive: true, force: true });
  }
}

describe("ApplicationStack", () => {
  test("creates an API, Python Lambda asset, and DynamoDB table", () => {
    const app = new cdk.App();
    const stack = new ApplicationStack(app, stackNameForEnvironment("pr-42", "feature/Add_Login"), {
      environment: "pr-42", previewBranch: "feature/Add_Login",
    });
    expect(stack.stackName).toBe("app-feature-add-login");
    const template = Template.fromStack(stack);
    template.resourceCountIs("AWS::DynamoDB::Table", 1);
    template.hasResourceProperties("AWS::Lambda::Function", {
      Runtime: "python3.12",
      Handler: "handler.handler",
      Code: Match.objectLike({ S3Key: Match.anyValue() }),
      Environment: { Variables: Match.objectLike({ APP_ENVIRONMENT: "pr-42" }) },
    });
    template.resourceCountIs("AWS::ApiGateway::RestApi", 1);
  });

  test("retains DynamoDB data only in production", () => {
    const production = Template.fromStack(new ApplicationStack(new cdk.App(), "Production", { environment: "production" }));
    const preview = Template.fromStack(new ApplicationStack(new cdk.App(), "Preview", {
      environment: "pr-42", previewBranch: "feature/Add_Login",
    }));
    production.hasResource("AWS::DynamoDB::Table", { DeletionPolicy: "Retain" });
    preview.hasResource("AWS::DynamoDB::Table", { DeletionPolicy: "Delete" });
  });

  test.each([["development", "app-development"], ["staging", "app-staging"], ["production", "app-production"]])(
    "uses an environment-scoped stack name for %s",
    (environment, expected) => expect(stackNameForEnvironment(environment)).toBe(expected),
  );

  test("rejects a stack environment that cannot be safely targeted", () => {
    expect(() => stackNameForEnvironment("prod")).toThrow("environment must be");
    expect(() => stackNameForEnvironment("pr-42")).toThrow("previewBranch");
    expect(() => stackNameForEnvironment("pr-0", "feature/x")).toThrow();
  });

  test.each([
    ["feature/Add_Login", "app-feature-add-login"],
    ["fix/API_Error", "app-fix-api-error"],
    ["--A__B--", "app-a--b"],
    ["a".repeat(29) + "/long", "app-" + "a".repeat(29)],
    ["a".repeat(28) + "//long", "app-" + "a".repeat(28)],
    ["a".repeat(31), "app-" + "a".repeat(30)],
    ["日本語/Feature", "app-feature"],
    ["a😀b", "app-a-b"],
  ])("uses the common branch naming rule for %s", (branch, expected) => {
    expect(previewStackName(branch)).toBe(expected);
    expect(stackNameForEnvironment("pr-42", branch)).toBe(expected);
    expect(stackNameForEnvironment("pr-99", branch)).toBe(expected);
  });

  test.each(["", "---", "日本語", "Development", "-staging-", "PRODUCTION", "development" + "-".repeat(30) + "x"])(
    "rejects empty or shared preview name %s", (branch) => {
      expect(() => stackNameForEnvironment("pr-42", branch)).toThrow();
    },
  );

  test("synthesizes the resolved physical stack name and ownership tags", () => {
    const app = new cdk.App();
    const stack = new ApplicationStack(app, "DifferentConstructId", {
      environment: "pr-42", previewBranch: "feature/Add_Login",
    });
    const artifact = app.synth().getStackArtifact(stack.artifactId);
    expect(artifact.stackName).toBe("app-feature-add-login");
    expect(artifact.tags).toMatchObject({
      "app:managed-by": "ai-driven-development", "app:preview-pr": "42",
    });
    expect(() => new ApplicationStack(new cdk.App(), "Wrong", {
      environment: "pr-42", previewBranch: "feature/Add_Login", stackName: "app-wrong",
    })).toThrow("stackName does not match");
  });

  test("excludes Python tests from the Lambda asset without masking implementation changes", () => {
    const fixtureDirectory = mkdtempSync(join(tmpdir(), "ai-driven-development-lambda-"));
    const handlerPath = join(fixtureDirectory, "handler.py");
    const testPath = join(fixtureDirectory, "handler_test.py");
    const nestedDirectory = join(fixtureDirectory, "nested");
    const nestedTestPath = join(nestedDirectory, "handler_test.py");

    try {
      writeFileSync(handlerPath, "def handler(event, context):\n    return {'statusCode': 200}\n");
      writeFileSync(testPath, "def test_handler() -> None:\n    pass\n");
      mkdirSync(nestedDirectory, { recursive: true });
      writeFileSync(nestedTestPath, "def test_nested_handler() -> None:\n    pass\n");

      const initialAsset = lambdaAsset(fixtureDirectory);
      expect(initialAsset.files).toEqual(["handler.py"]);

      writeFileSync(testPath, "def test_handler() -> None:\n    assert True\n");
      expect(lambdaAsset(fixtureDirectory).hash).toBe(initialAsset.hash);

      writeFileSync(handlerPath, "def handler(event, context):\n    return {'statusCode': 201}\n");
      expect(lambdaAsset(fixtureDirectory).hash).not.toBe(initialAsset.hash);
    } finally {
      rmSync(fixtureDirectory, { recursive: true, force: true });
    }
    expect(existsSync(fixtureDirectory)).toBe(false);
  });
});
