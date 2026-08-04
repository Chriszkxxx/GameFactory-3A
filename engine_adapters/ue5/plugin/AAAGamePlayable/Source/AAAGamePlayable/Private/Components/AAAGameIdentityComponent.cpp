#include "Components/AAAGameIdentityComponent.h"

#include "GameFramework/Actor.h"
#include "Net/UnrealNetwork.h"

UAAAGameIdentityComponent::UAAAGameIdentityComponent()
{
    SetIsReplicatedByDefault(true);
}

void UAAAGameIdentityComponent::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);

    DOREPLIFETIME(UAAAGameIdentityComponent, ParticipantId);
    DOREPLIFETIME(UAAAGameIdentityComponent, EntityId);
}

void UAAAGameIdentityComponent::SetRuntimeIdentity(
    const FString& InParticipantId,
    const FString& InEntityId)
{
    const AActor* Owner = GetOwner();
    if (Owner && !Owner->HasAuthority())
    {
        return;
    }

    ParticipantId = InParticipantId;
    EntityId = InEntityId;
}
