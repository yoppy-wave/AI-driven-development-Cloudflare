import * as cdk from "aws-cdk-lib";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { Construct } from "constructs";
import { previewStackName } from "./preview-stack-name.cjs";

const APPLICATION_NAME = "app";
const SHARED_ENVIRONMENTS = new Set(["development", "staging", "production"]);

export function stackNameForEnvironment(environment: string, previewBranch?: string): string {
  if (SHARED_ENVIRONMENTS.has(environment)) {
    return `${APPLICATION_NAME}-${environment}`;
  }
  if (/^pr-[1-9][0-9]*$/.test(environment) && previewBranch !== undefined) {
    return previewStackName(previewBranch);
  }
  throw new Error("environment must be development, staging, production, or pr-<positive number> with previewBranch");
}

export interface ApplicationStackProps extends cdk.StackProps {
  readonly environment: string;
  readonly previewBranch?: string;
  readonly lambdaAssetPath?: string;
}

export class ApplicationStack extends cdk.Stack {
  public constructor(scope: Construct, id: string, props: ApplicationStackProps) {
    const stackName = stackNameForEnvironment(props.environment, props.previewBranch);
    if (props.stackName !== undefined && props.stackName !== stackName) {
      throw new Error("stackName does not match the environment/preview branch");
    }
    super(scope, id, { ...props, stackName });

    cdk.Tags.of(this).add("app:managed-by", "ai-driven-development");
    cdk.Tags.of(this).add("app:environment", props.environment);
    if (props.environment.startsWith("pr-")) {
      cdk.Tags.of(this).add("app:preview-pr", props.environment.slice(3));
    }

    const table = new dynamodb.Table(this, "Items", {
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: props.environment === "production" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    const handler = new lambda.Function(this, "ApiHandler", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(props.lambdaAssetPath ?? "lambda", {
        exclude: ["__pycache__", ".pytest_cache", "**/*_test.py", "*.pyc"],
      }),
      environment: {
        ITEMS_TABLE_NAME: table.tableName,
        APP_ENVIRONMENT: props.environment,
      },
    });
    table.grantReadWriteData(handler);

    const api = new apigateway.LambdaRestApi(this, "Api", { handler, proxy: true });
    new cdk.CfnOutput(this, "ApiUrl", { value: api.url });
  }
}
