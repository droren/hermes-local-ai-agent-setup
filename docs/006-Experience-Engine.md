# 006 - Experience Engine

## Purpose

The Experience Engine turns repeated work into reusable procedures without requiring continuous model fine-tuning.

## Inputs

- task plans;
- operator edits;
- review findings;
- test results;
- failed attempts;
- model/backend selections;
- execution time and resource use;
- accepted final artifacts.

## Outputs

- reusable workflow patterns;
- capability confidence scores;
- routing preferences;
- suggested task decomposition templates;
- learned content or coding conventions;
- warnings about known failure modes.

## Example: product creation workflow

After observing multiple manually corrected product entries, the engine can learn a structured procedure such as:

1. identify product family;
2. extract supplier facts;
3. normalize naming;
4. generate description in the site's established style;
5. validate mandatory attributes;
6. compare against prior accepted products;
7. request approval until confidence threshold is reached.

The learned object is a procedure and evidence set, not a hidden claim that the base model has been retrained.
