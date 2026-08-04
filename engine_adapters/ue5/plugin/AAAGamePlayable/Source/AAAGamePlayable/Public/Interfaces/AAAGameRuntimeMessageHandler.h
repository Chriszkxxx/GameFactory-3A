#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "AAAGameRuntimeMessageHandler.generated.h"

UINTERFACE(BlueprintType)
class AAAGAMEPLAYABLE_API UAAAGameRuntimeMessageHandler : public UInterface
{
    GENERATED_BODY()
};

class AAAGAMEPLAYABLE_API IAAAGameRuntimeMessageHandler
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AAAGame|Runtime")
    bool HandleRuntimeMessage(
        const FString& MessageType,
        const FString& JsonPayload);
};
