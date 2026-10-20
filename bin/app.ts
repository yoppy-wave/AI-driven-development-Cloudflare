#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ApplicationStack, stackNameForEnvironment } from "../lib/application-stack";

const app = new cdk.App();
const environment = app.node.tryGetContext("environment") as string | undefined;

if (!environment) {
  throw new Error("The CDK context value 'environment' is required.");
}

const previewBranch = app.node.tryGetContext("previewBranch") as string | undefined;
new ApplicationStack(app, stackNameForEnvironment(environment, previewBranch), { environment, previewBranch });
